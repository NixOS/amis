import boto3
import logging


def get_public_ami_service_quota(servicequotas):
    return next(servicequotas
                .get_paginator('list_service_quotas')
                .paginate(ServiceCode="ec2")
                .search("Quotas[?QuotaName=='Public AMIs']"))


def main():
    logging.basicConfig(level=logging.INFO)
    ec2 = boto3.client("ec2")
    regions = ec2.describe_regions()["Regions"]
    for region in regions:
        servicequotas = boto3.client(
            "service-quotas", region_name=region["RegionName"])
        service_quota = get_public_ami_service_quota(servicequotas)
        try:
            desired_value = 100
            if service_quota['Value'] >= desired_value:
                logging.info(
                    f"Quota for {region['RegionName']} is already {service_quota['Value']}")
                continue
            logging.info(
                f"Requesting quota increase for {region['RegionName']}")
            servicequotas.request_service_quota_increase(
                ServiceCode="ec2",
                QuotaCode=service_quota['QuotaCode'],
                DesiredValue=100,
            )
        except Exception as e:
            logging.warn(e)


if __name__ == "__main__":
    main()
