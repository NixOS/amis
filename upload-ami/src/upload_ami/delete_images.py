import logging
from telnetlib import EC
import boto3
from mypy_boto3_ec2 import EC2Client
import argparse

logger = logging.getLogger(__name__)


def delete_images_by_name(ec2: EC2Client, image_name: str) -> None:
    """
    Delete an image by its name.

    Name can be a filter

    Idempotent, unlike delete_image_by_id
    """
    logger.info(f"Deleting image by name {image_name}")
    snapshots = ec2.describe_snapshots(
        OwnerIds=["self"], Filters=[{"Name": "tag:Name", "Values": [image_name]}]
    )
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
        for image in images["Images"]:
            assert "ImageId" in image
            logger.info(f"Deregistering {image['ImageId']}")
            ec2.deregister_image(ImageId=image["ImageId"])
        logger.info(f"Deleting {snapshot['SnapshotId']}")
        ec2.delete_snapshot(SnapshotId=snapshot["SnapshotId"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--image-name",
        type=str,
        required=True,
        help="Name of the image to delete. Can be a filter.",
    )
    parser.add_argument(
        "--all-regions",
        action="store_true",
    )
    logging.basicConfig(level=logging.INFO)
    ec2: EC2Client = boto3.client("ec2", region_name="us-east-1")

    args = parser.parse_args()
    delete_images_by_name(ec2, args.image_name)
    if args.all_regions:
        regions = ec2.describe_regions()["Regions"]
        for region in regions:
            assert "RegionName" in region
            ec2r = boto3.client("ec2", region_name=region["RegionName"])
            logger.info(f"Deleting image by name {args.image_name} in {region['RegionName']}")
            delete_images_by_name(ec2r, args.image_name)


if __name__ == "__main__":
    main()
