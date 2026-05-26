import argparse
import logging
import boto3
import json

from mypy_boto3_ec2 import EC2Client


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--best-effort-region",
        help="Regions where failures are logged as warnings instead of errors",
        action="append",
        default=[],
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    ec2: EC2Client = boto3.client("ec2")
    regions = ec2.describe_regions()["Regions"]

    images = {}

    for region in regions:
        assert "RegionName" in region
        region_name = region["RegionName"]
        ec2r = boto3.client("ec2", region_name=region_name)

        try:
            result = ec2r.describe_images(
                Owners=["self"],
                ExecutableUsers=["all"],
            )
        except Exception as e:
            if region_name not in args.best_effort_region:
                raise
            logging.warning(
                f"Describing images in {region_name} failed (best-effort, ignoring): {e}"
            )
            continue
        images[region_name] = result

    print(json.dumps(images, indent=2))


if __name__ == "__main__":
    main()
