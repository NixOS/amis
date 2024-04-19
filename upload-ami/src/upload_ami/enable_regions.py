import boto3
from mypy_boto3_account import AccountClient
import logging


def main() -> None:
    """
    Enable all regions that are disabled

    Due to rate limiting, you might  need to run this multiple times.
    """
    logging.basicConfig(level=logging.INFO)
    account: AccountClient = boto3.client("account")
    pages = account.get_paginator("list_regions").paginate(
        RegionOptStatusContains=["DISABLED"]
    )
    for page in pages:
        for region in page["Regions"]:
            assert "RegionName" in region
            logging.info(f"enabling region {region['RegionName']}")
            account.enable_region(RegionName=region["RegionName"])
