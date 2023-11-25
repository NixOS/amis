import json
import hashlib
import logging
import boto3
import botocore
import botocore.exceptions
from concurrent.futures import ThreadPoolExecutor


def upload_to_s3_if_not_exists(s3, bucket, key, file):
    """
    Upload file to S3 if it doesn't exist yet

    This function is idempotent.
    """
    try:
        logging.info(f"Checking if s3://{bucket}/{key} exists")
        s3.head_object(Bucket=bucket, Key=key)
    except botocore.exceptions.ClientError as e:
        logging.info(f"Uploading {file} to s3://{bucket}/{key}")
        s3.upload_file(file, bucket, key)
        s3.get_waiter("object_exists").wait(Bucket=bucket, Key=key)


def import_snapshot(ec2, s3_bucket, image_name):
    """
    Import snapshot from S3 and wait for it to finish

    This function is idempotent by using the image_name as the client token

    Returns the snapshot id
    """
    logging.info(f"Importing s3://{s3_bucket}/{image_name} to EC2")
    client_token = hashlib.sha256(image_name.encode()).hexdigest()
    # TODO: I'm not sure how long AWS keeps track of import_snapshot_tasks and
    # thus if we can rely on the client token forever. E.g. what happens if I
    # run a task with the same client token a few months later?
    snapshot_import_task = ec2.import_snapshot(
        DiskContainer={
            "Format": "VHD",
            "UserBucket": {"S3Bucket": s3_bucket, "S3Key": image_name},
        },
        ClientToken=client_token,
    )
    ec2.get_waiter("snapshot_imported").wait(
        ImportTaskIds=[snapshot_import_task["ImportTaskId"]]
    )

    snapshot_import_tasks = ec2.describe_import_snapshot_tasks(
        ImportTaskIds=[snapshot_import_task["ImportTaskId"]]
    )
    assert len(snapshot_import_tasks["ImportSnapshotTasks"]) != 0
    snapshot_import_task = snapshot_import_tasks["ImportSnapshotTasks"][0]
    return snapshot_import_task["SnapshotTaskDetail"]["SnapshotId"]


def register_image_if_not_exists(ec2, image_name, image_info, snapshot_id):
    """
    Register image if it doesn't exist yet

    This function is idempotent because image_name is unique
    """
    describe_images = ec2.describe_images(
        Owners=["self"], Filters=[{"Name": "name", "Values": [image_name]}]
    )
    if len(describe_images["Images"]) != 0:
        image_id = describe_images["Images"][0]["ImageId"]
    else:
        if image_info["system"] == "x86_64-linux":
            architecture = "x86_64"
        elif image_info["system"] == "aarch64-linux":
            architecture = "arm64"
        else:
            raise Exception("Unknown system: " + image_info["system"])

        logging.info(f"Registering image {image_name} with snapshot {snapshot_id}")
        register_image = ec2.register_image(
            Name=image_name,
            Architecture=architecture,
            BootMode=image_info["boot_mode"],
            BlockDeviceMappings=[
                {
                    "DeviceName": "/dev/xvda",
                    "Ebs": {
                        "SnapshotId": snapshot_id,
                        "VolumeType": "gp3",
                    },
                }
            ],
            RootDeviceName="/dev/xvda",
            VirtualizationType="hvm",
            EnaSupport=True,
            SriovNetSupport="simple",
            TpmSupport="v2.0" if architecture == "x86_64" else None,
        )
        image_id = register_image["ImageId"]

    ec2.get_waiter("image_available").wait(ImageIds=[image_id])
    return image_id


def copy_image_to_regions(image_id, image_name, source_region, target_regions):
    """
    Copy image to all target regions

    Copies to all regions in parallel and waits for all of them to finish

    This function is idempotent because image_id is unique and we use it
    as the client_token for the copy_image task
    """

    def copy_image(image_id, image_name, source_region, target_region):
        """
        Copy image to target_region

        This function is idempotent because image_id is unique and we use it as
        the client_token for the copy_image task.

        TODO: How long can we rely on the client_token? E.g. what happens if I rerun this
        script a few months later?

        """
        ec2r = boto3.client("ec2", region_name=target_region)
        logging.info(
            f"Copying image {image_id} from {source_region} to {target_region}"
        )
        copy_image = ec2r.copy_image(
            SourceImageId=image_id,
            SourceRegion=source_region,
            Name=image_name,
            ClientToken=image_id,
        )
        ec2r.get_waiter("image_available").wait(ImageIds=[copy_image["ImageId"]])
        logging.info(
            f"Finished image {image_id} from {source_region} to {target_region}"
        )
        return (target_region, copy_image["ImageId"])

    with ThreadPoolExecutor() as executor:
        image_ids = dict(
            executor.map(
                lambda target_region: copy_image(
                    image_id, image_name, source_region, target_region
                ),
                target_regions,
            )
        )

    image_ids[source_region] = image_id
    return image_ids


def upload_ami(image_info_path, s3_bucket, regions):
    """
    Upload NixOS AMI to AWS and return the image ids for each region

    This function is idempotent because all the functions it calls are idempotent.
    """
    ec2 = boto3.client("ec2")
    s3 = boto3.client("s3")

    with open(image_info_path, "r") as f:
        image_info = json.load(f)

    image_name = "nixos-" + image_info["label"] + "-" + image_info["system"]
    image_file = image_info["file"]

    upload_to_s3_if_not_exists(s3, s3_bucket, image_name, image_file)
    snapshot_id = import_snapshot(ec2, s3_bucket, image_name)
    image_id = register_image_if_not_exists(ec2, image_name, image_info, snapshot_id)
    image_ids = copy_image_to_regions(
        image_id, image_name, ec2.meta.region_name, regions
    )

    print(json.dumps(image_ids))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload NixOS AMI to AWS")
    parser.add_argument("--image-info", help="Path to image info", required=True)
    parser.add_argument("--s3-bucket", help="S3 bucket to upload to", required=True)
    parser.add_argument("--region", nargs="+", help="Regions to upload to")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level)

    upload_ami(args.image_info, args.s3_bucket, args.region)
