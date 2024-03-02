import boto3
import time
import argparse
import logging


def smoke_test(image_id, run_id, cancel):
    ec2 = boto3.client("ec2")

    images = ec2.describe_images(Owners=["self"], ImageIds=[image_id])
    assert len(images["Images"]) == 1
    image = images["Images"][0]
    architecture = image["Architecture"]
    if architecture == "x86_64":
        instance_type = "t3a.nano"
    elif architecture == "arm64":
        instance_type = "t4g.nano"
    else:
        raise Exception("Unknown architecture: " + architecture)

    logging.info("Starting instance")
    run_instances = ec2.run_instances(
        ImageId=image_id,
        InstanceType=instance_type,
        MinCount=1,
        MaxCount=1,
        ClientToken=image_id + run_id if run_id else image_id,
        InstanceMarketOptions={"MarketType": "spot"},
    )

    instance_id = run_instances["Instances"][0]["InstanceId"]

    try:
        if not cancel:
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
        ec2.terminate_instances(InstanceIds=[instance_id])
        ec2.get_waiter("instance_terminated").wait(InstanceIds=[instance_id])


def main():
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--run-id", required=False)
    parser.add_argument("--cancel", action="store_true", required=False)
    args = parser.parse_args()

    smoke_test(args.image_id, args.run_id, args.cancel)


if __name__ == "__main__":
    main()
