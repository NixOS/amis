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
            deprecation_time = image.get("DeprecationTime")
            if deprecation_time:
                current_time = datetime.datetime.now(deprecation_time.tzinfo)
                deprecation_time = datetime.datetime.strptime(
                    deprecation_time, "%Y-%m-%dT%H:%M:%SZ"
                )
                if current_time >= deprecation_time:
                    logger.info(f"Deleting image {image['ImageId']}")
                    try:
                        ec2.deregister_image(ImageId=image["ImageId"], DryRun=dry_run)
                    except botocore.exceptions.ClientError as e:
                        if "DryRunOperation" in str(e):
                            logger.info(f"Would have deleted image {image['ImageId']}")
                        else:
                            raise
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
    ec2: EC2Client = boto3.client("ec2")

    args = parser.parse_args()
    regions = ec2.describe_regions()["Regions"]
    for region in regions:
        assert "RegionName" in region
        ec2r = boto3.client("ec2", region_name=region["RegionName"])
        logger.info(
            f"Deleting image by name {args.image_name} in {region['RegionName']}"
        )
        delete_deprecated_images(ec2r, args.dry_run)


if __name__ == "__main__":
    main()
