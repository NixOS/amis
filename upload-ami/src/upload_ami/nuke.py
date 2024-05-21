import logging
import boto3
from mypy_boto3_ec2 import EC2Client
import argparse
import botocore.exceptions


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
    )
    parser.add_argument(
        "--older-than",
        type=str,
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    ec2: EC2Client = boto3.client("ec2", region_name="us-east-1")

    regions = ec2.describe_regions()["Regions"]

    for region in regions:
        assert "RegionName" in region
        ec2r = boto3.client("ec2", region_name=region["RegionName"])
        logging.info(f"Nuking {region['RegionName']}")
        images = ec2r.describe_images(
            Owners=["self"], Filters=[{"Name": "name", "Values": [args.image_name]}]
        )
        for image in images["Images"]:
            snapshot_id = image["BlockDeviceMappings"][0]["Ebs"]["SnapshotId"]
            logging.info(f"Deregistering {image['ImageId']}")
            try:
                ec2r.deregister_image(ImageId=image["ImageId"], DryRun=args.dry_run)
            except botocore.exceptions.ClientError as e:
                if "DryRunOperation" not in str(e):
                    raise
            logging.info(f"Deleting {snapshot_id}")
            try:
                ec2r.delete_snapshot(SnapshotId=snapshot_id, DryRun=args.dry_run)
            except botocore.exceptions.ClientError as e:
                if "DryRunOperation" not in str(e):
                    raise


if __name__ == "__main__":
    main()
