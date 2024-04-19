import logging
import boto3
import json

from mypy_boto3_ec2 import EC2Client


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ec2: EC2Client = boto3.client("ec2")
    regions = ec2.describe_regions()["Regions"]

    images = {}

    for region in regions:
        assert "RegionName" in region
        ec2r = boto3.client("ec2", region_name=region["RegionName"])

        result = ec2r.describe_images(
            Owners=["self"],
            ExecutableUsers=["all"],
        )
        images[region["RegionName"]] = result

    print(json.dumps(images, indent=2))


if __name__ == "__main__":
    main()
