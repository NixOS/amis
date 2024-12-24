import logging
import boto3
from mypy_boto3_ec2 import EC2Client
import argparse
import botocore.exceptions


def delete_orphaned_snapshots(ec2: EC2Client, dry_run: bool) -> None:
    snapshot_paginator = ec2.get_paginator("describe_snapshots")
    snapshot_iterator = snapshot_paginator.paginate(
        OwnerIds=["self"], Filters=[{"Name": "tag:ManagedBy", "Values": ["NixOS/amis"]}]
    )
    for pages in snapshot_iterator:
        for snapshot in pages["Snapshots"]:
            assert "SnapshotId" in snapshot
            snapshot_id = snapshot["SnapshotId"]
            logging.info(f"Checking snapshot {snapshot_id}")
            images = ec2.describe_images(
                Filters=[
                    {
                        "Name": "block-device-mapping.snapshot-id",
                        "Values": [snapshot_id],
                    }
                ],
                MaxResults=6,
            )
            if len(images["Images"]) == 0:
                logging.info(f"Deleting orphaned snapshot {snapshot_id}")
                try:
                    ec2.delete_snapshot(SnapshotId=snapshot_id, DryRun=dry_run)
                except botocore.exceptions.ClientError as e:
                    if "DryRunOperation" in str(e):
                        logging.info(
                            f"Would have deleted orphaned snapshot {snapshot_id}"
                        )
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
        ec2 = boto3.client("ec2", region_name=region["RegionName"])
        logging.info(f"Checking region {region['RegionName']}")
        delete_orphaned_snapshots(ec2, args.dry_run)
