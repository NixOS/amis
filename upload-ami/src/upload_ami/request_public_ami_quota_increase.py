import boto3
import logging


def get_public_ami_service_quota(servicequotas):
    return next(servicequotas
                .get_paginator('list_service_quotas')
                .paginate(ServiceCode="ec2")
                .search("Quotas[?QuotaName=='Public AMIs']"))


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--desired-value", type=int, default=1000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    ec2 = boto3.client("ec2")
    regions = ec2.describe_regions()["Regions"]
    for region in regions:
        servicequotas = boto3.client(
            "service-quotas", region_name=region["RegionName"])
        service_quota = get_public_ami_service_quota(servicequotas)
        logging.info(
            f"Quota for {region['RegionName']} is  {service_quota['Value']}")
        try:
            if service_quota['Value'] < args.desired_value:
                logging.info(
                    f"Requesting quota increase for {region['RegionName']} from  {service_quota['Value']} to {args.desired_value}")
                servicequotas.request_service_quota_increase( ServiceCode="ec2", QuotaCode=service_quota['QuotaCode'], DesiredValue=args.desired_value)
        except Exception as e:
            logging.warn(e)


if __name__ == "__main__":
    main()
