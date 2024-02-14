import logging
import boto3
import json

def main():
    logging.basicConfig(level=logging.INFO)
    ec2 = boto3.client("ec2")
    regions = ec2.describe_regions()["Regions"]

    images = {}

    for region in regions:
        ec2r = boto3.client("ec2", region_name=region["RegionName"])

        result = ec2r.describe_images(
            Owners=["self"],
            ExecutableUsers=["all"],
        )
        images[region["RegionName"]] = result
    
    print(json.dumps(images, indent=2))

if __name__ == "__main__":
    main()