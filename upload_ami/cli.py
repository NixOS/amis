import json
import hashlib
import logging
import boto3
import botocore
import botocore.exceptions
from concurrent.futures import ThreadPoolExecutor


def upload_ami(nix_store_path, s3_bucket, regions):
    with open(nix_store_path + "/nix-support/image-info.json", "r") as f:
        image_info = json.load(f)

    image_name = "nixos-" + image_info["label"] + "-" + image_info["system"]

    ec2 = boto3.client("ec2")
    s3 = boto3.client("s3")

    try:
        logging.info(f"Checking if s3://{s3_bucket}/{image_name} exists")
        s3.head_object(Bucket=s3_bucket, Key=image_name)
    except botocore.exceptions.ClientError as e:
        logging.info(f'Uploading {image_info["file"]} to s3://{s3_bucket}/{image_name}')
        s3.upload_file(image_info["file"], s3_bucket, image_name)
        s3.get_waiter("object_exists").wait(Bucket=s3_bucket, Key=image_name)

    logging.info(f"Importing s3://{s3_bucket}/{image_name} to EC2")
    client_token = hashlib.sha256(image_name.encode()).hexdigest()
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
    snapshot_id = snapshot_import_task["SnapshotTaskDetail"]["SnapshotId"]

    describe_images = ec2.describe_images(
        Owners=["self"], Filters=[{"Name": "name", "Values": [image_name]}]
    )

    source_region = ec2.meta.region_name
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
                    "Ebs": {"SnapshotId": snapshot_id},
                }
            ],
            RootDeviceName="/dev/xvda",
            VirtualizationType="hvm",
            EnaSupport=True,
            SriovNetSupport="simple",
        )
        image_id = register_image["ImageId"]
    ec2.get_waiter("image_available").wait(ImageIds=[image_id])

    image_ids = {}

    def copy_image(image_id, image_name, source_region, target_region):
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
                regions,
            )
        )

    image_ids[source_region] = image_id

    print(json.dumps(image_ids))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Upload NixOS AMI to AWS")
    parser.add_argument("--nix-store-path", help="Path to nix store")
    parser.add_argument("--bucket", help="S3 bucket to upload to")
    parser.add_argument("--region", nargs="+", help="Regions to upload to")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level)

    upload_ami(args.nix_store_path, args.s3_bucket, args.regions)
