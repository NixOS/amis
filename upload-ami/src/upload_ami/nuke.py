import logging
import boto3
from mypy_boto3_ec2 import EC2Client


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ec2: EC2Client = boto3.client("ec2", region_name="us-east-1")

    regions = ec2.describe_regions()["Regions"]

    for region in regions:
        assert "RegionName" in region
        ec2r = boto3.client("ec2", region_name=region["RegionName"])
        logging.info(f"Nuking {region['RegionName']}")
        snapshots = ec2r.describe_snapshots(OwnerIds=["self"])
        for snapshot in snapshots["Snapshots"]:

            assert "SnapshotId" in snapshot
            images = ec2r.describe_images(
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
                logging.info(f"Deregistering {image['ImageId']}")
                ec2r.deregister_image(ImageId=image["ImageId"])

            logging.info(f"Deleting {snapshot['SnapshotId']}")
            ec2r.delete_snapshot(SnapshotId=snapshot["SnapshotId"])


if __name__ == "__main__":
    main()
