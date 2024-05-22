import logging
import boto3
from mypy_boto3_ec2 import EC2Client
import argparse
import botocore.exceptions

logger = logging.getLogger(__name__)


def delete_images_by_name(ec2: EC2Client, image_name: str, dry_run: bool) -> None:
    """
    Delete an image by its name.

    Name can be a filter

    Idempotent, unlike nuke
    """
    logger.info(f"Deleting image by name {image_name}")
    snapshots = ec2.describe_snapshots(
        OwnerIds=["self"], Filters=[{"Name": "tag:Name", "Values": [image_name]}]
    )
    logger.info(f"Deleting {len(snapshots['Snapshots'])} snapshots")

    for snapshot in snapshots["Snapshots"]:
        assert "SnapshotId" in snapshot
        images = ec2.describe_images(
            Owners=["self"],
            Filters=[
                {
                    "Name": "block-device-mapping.snapshot-id",
                    "Values": [snapshot["SnapshotId"]],
                }
            ],
        )
        logger.info(f"Deleting {len(images['Images'])} images")
        for image in images["Images"]:
            assert "ImageId" in image
            logger.info(f"Deregistering {image['ImageId']}")
            try:
                ec2.deregister_image(ImageId=image["ImageId"], DryRun=dry_run)
            except botocore.exceptions.ClientError as e:
                if "DryRunOperation" not in str(e):
                    raise e

        logger.info(f"Deleting {snapshot['SnapshotId']}")
        try:
            ec2.delete_snapshot(SnapshotId=snapshot["SnapshotId"], DryRun=dry_run)
        except botocore.exceptions.ClientError as e:
            if "DryRunOperation" not in str(e):
                raise e


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image-name",
        type=str,
        required=True,
        help="Name of the image to delete. Can be a filter.",
    )

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
        delete_images_by_name(ec2r, args.image_name, args.dry_run)


if __name__ == "__main__":
    main()
