import boto3
import botocore.exceptions
import time
import argparse
import logging

from mypy_boto3_ec2 import EC2Client
from mypy_boto3_ec2.literals import InstanceTypeType


def smoke_test(image_id: str, run_id: str, cancel: bool) -> None:
    ec2: EC2Client = boto3.client("ec2")

    images = ec2.describe_images(Owners=["self"], ImageIds=[image_id])
    assert len(images["Images"]) == 1
    image = images["Images"][0]
    assert "Architecture" in image
    architecture = image["Architecture"]
    instance_type: InstanceTypeType
    if architecture == "x86_64":
        instance_type = "t3.nano"
    elif architecture == "arm64":
        instance_type = "t4g.nano"
    else:
        raise Exception("Unknown architecture: " + architecture)
    logging.info("Starting instance")
    try:
        run_instances = ec2.run_instances(
            ImageId=image_id,
            InstanceType=instance_type,
            MinCount=1,
            MaxCount=1,
            ClientToken=image_id + run_id if run_id else image_id,
            InstanceMarketOptions={"MarketType": "spot"},
        )
    except botocore.exceptions.ClientError as error:
        if error.response["Error"]["Code"] == "IdempotentInstanceTerminated":
            logging.warn(error)
            return
        else:
            raise error

    instance = run_instances["Instances"][0]
    assert "InstanceId" in instance
    assert "State" in instance
    assert "Name" in instance["State"]
    instance_id = instance["InstanceId"]
    try:
        if cancel or instance["State"]["Name"] == "terminated":
            return
        # This basically waits for DHCP to have finished; as it uses ARP to check if the instance is healthy
        logging.info(f"Waiting for instance {instance_id} to be running")
        ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])
        logging.info(f"Waiting for instance {instance_id} to be healthy")
        ec2.get_waiter("instance_status_ok").wait(InstanceIds=[instance_id])
        tries = 5
        console_output = ec2.get_console_output(InstanceId=instance_id, Latest=True)
        output = console_output.get("Output")
        while not output and tries > 0:
            time.sleep(10)
            logging.info(
                f"Waiting for console output to become available ({tries} tries left)"
            )
            console_output = ec2.get_console_output(InstanceId=instance_id, Latest=True)
            output = console_output.get("Output")
            tries -= 1
        logging.info(f"Console output: {output}")
    except Exception as e:
        logging.error(f"Error: {e}")
        raise
    finally:
        logging.info(f"Terminating instance {instance_id}")
        if instance["State"]["Name"] != "terminated":
            ec2.terminate_instances(InstanceIds=[instance_id])
            ec2.get_waiter("instance_terminated").wait(InstanceIds=[instance_id])


def main() -> None:
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--run-id", required=False)
    parser.add_argument("--cancel", action="store_true", required=False)
    args = parser.parse_args()

    smoke_test(args.image_id, args.run_id, args.cancel)


if __name__ == "__main__":
    main()
