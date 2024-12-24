import logging
import boto3
from mypy_boto3_ec2 import EC2Client
import argparse
import botocore.exceptions
import datetime

logger = logging.getLogger(__name__)


def delete_deprecated_images(ec2: EC2Client, dry_run: bool) -> None:
    """
    Delete an image by its name.

    Name can be a filter

    Idempotent, unlike nuke
    """

    images_paginator = ec2.get_paginator("describe_images")
    images_iterator = images_paginator.paginate(Owners=["self"])
    for pages in images_iterator:
        for image in pages["Images"]:
            if "DeprecationTime" in image:
                # HACK: As python can not parse ISO8601 strings with
                # milliseconds, but it **can** produce them, instead of parsing
                # the datetime from the API, we format the current time as an
                # ISO8601 string and compare the strings. This works because
                # ISO8601 strings are lexicographically comparable.
                current_time = datetime.datetime.isoformat(
                    datetime.datetime.now(), timespec="milliseconds"
                )
                if current_time >= image["DeprecationTime"]:
                    assert "ImageId" in image
                    assert "Name" in image
                    logger.info(f"Deleting image {image['Name']} : {image['ImageId']}. DeprecationTime: {image['DeprecationTime']}")
                    try:
                        ec2.deregister_image(ImageId=image["ImageId"], DryRun=dry_run)
                    except botocore.exceptions.ClientError as e:
                        if "DryRunOperation" in str(e):
                            logger.info(f"Would have deleted image {image['ImageId']}")
                        else:
                            raise
                    assert "BlockDeviceMappings" in image
                    assert "Ebs" in image["BlockDeviceMappings"][0]
                    assert "SnapshotId" in image["BlockDeviceMappings"][0]["Ebs"]
                    snapshot_id = image["BlockDeviceMappings"][0]["Ebs"]["SnapshotId"]
                    logger.info(f"Deleting snapshot {snapshot_id}")
                    try:
                        ec2.delete_snapshot(SnapshotId=snapshot_id, DryRun=dry_run)
                    except botocore.exceptions.ClientError as e:
                        if "DryRunOperation" in str(e):
                            logger.info(f"Would have deleted snapshot {snapshot_id}")
                        else:
                            raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not actually delete anything, just log what would be deleted",
    )
    logging.basicConfig(level=logging.INFO)
    ec2: EC2Client = boto3.client("ec2") # type: ignore 

    args = parser.parse_args()
    regions = ec2.describe_regions()["Regions"]
    for region in regions:
        assert "RegionName" in region
        ec2r = boto3.client("ec2", region_name=region["RegionName"]) # type: ignore 
        logging.info(f"Checking region {region['RegionName']}")
        delete_deprecated_images(ec2r, args.dry_run)


if __name__ == "__main__":
    main()
