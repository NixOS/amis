import boto3
import logging


def get_public_ami_service_quota(servicequotas):
    pages = servicequotas.get_paginator(
        'list_service_quotas').paginate(ServiceCode="ec2")
    for page in pages:
        for quota in page["Quotas"]:
            if quota["QuotaName"] == "Public AMIs":
                return quota
    raise Exception("No public AMI quota found")


def main():
    logging.basicConfig(level=logging.INFO)
    ec2 = boto3.client("ec2")
    regions = ec2.describe_regions()["Regions"]
    for region in regions:
        servicequotas = boto3.client(
            "service-quotas", region_name=region["RegionName"])
        service_quota = get_public_ami_service_quota(servicequotas)
        try:
            logging.info(f"Requesting quota increase for {region['RegionName']}")
            servicequotas.request_service_quota_increase(
                ServiceCode="ec2",
                QuotaCode=service_quota['QuotaCode'],
                DesiredValue=100,
            )
        except Exception as e:
            logging.warn(e)


if __name__ == "__main__":
    main()
