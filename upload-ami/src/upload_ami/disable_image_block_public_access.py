import boto3
import logging
import time
from concurrent.futures import ThreadPoolExecutor

def main():
    logging.basicConfig(level=logging.INFO)
    ec2 = boto3.client("ec2")
    regions = ec2.describe_regions()["Regions"]

    def disable_image_block_public_access(region):
        logging.info("disabling image block public access in %s. Can take some minutes to apply", region["RegionName"])
        ec2 = boto3.client("ec2", region_name=region["RegionName"])
        ec2.disable_image_block_public_access()

        while True:
            state = ec2.get_image_block_public_access_state()["ImageBlockPublicAccessState"]
            if state == "unblocked":
                break
            logging.info("waiting for image block public access state %s to be unblocked in %s", state, region["RegionName"])
            time.sleep(30)
    
    with ThreadPoolExecutor(max_workers=len(regions)) as executor:
        executor.map(disable_image_block_public_access, regions)

    
