from ast import List
from typing import Iterator
import boto3
import logging

from mypy_boto3_ec2 import EC2Client
from mypy_boto3_service_quotas import ServiceQuotasClient
from mypy_boto3_service_quotas.type_defs import (
    ListServiceQuotasResponseTypeDef,
    ServiceQuotaTypeDef,
)


def get_public_ami_service_quota(
    servicequotas: ServiceQuotasClient,
) -> ServiceQuotaTypeDef:
    paginator = servicequotas.get_paginator("list_service_quotas")
    searched: Iterator[ServiceQuotaTypeDef] = paginator.paginate(
        ServiceCode="ec2"
    ).search("Quotas[?QuotaName=='Public AMIs']")
    return next(searched)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--desired-value", type=int, default=1000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    ec2: EC2Client = boto3.client("ec2")
    regions = ec2.describe_regions()["Regions"]
    for region in regions:
        assert "RegionName" in region
        servicequotas: ServiceQuotasClient = boto3.client(
            "service-quotas", region_name=region["RegionName"]
        )
        service_quota = get_public_ami_service_quota(servicequotas)

        assert "Value" in service_quota
        logging.info(f"Quota for {region['RegionName']} is  {service_quota['Value']}")
        try:
            if service_quota["Value"] < args.desired_value:
                logging.info(
                    f"Requesting quota increase for {region['RegionName']} from  {service_quota['Value']} to {args.desired_value}"
                )
                servicequotas.request_service_quota_increase(
                    ServiceCode="ec2",
                    QuotaCode=service_quota["QuotaCode"],
                    DesiredValue=args.desired_value,
                )
        except Exception as e:
            logging.warn(e)


if __name__ == "__main__":
    main()
