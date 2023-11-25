import boto3
import time

def smoke_test(image_id, region):
    ec2 = boto3.client("ec2", region_name=region)

    # TODO per architecture
    run_instances = ec2.run_instances(ImageId=image_id, InstanceType="t3.micro", MinCount=1, MaxCount=1)
    logging.info(run_instances)

    instance_id = run_instances["Instances"][0]["InstanceId"]

    # This basically waits for DHCP to have finished; as it uses ARP to check if the instance is healthy
    ec2.get_waiter("instance_status_ok").wait(InstanceIds=[instance_id])

    console_output = ec2.get_console_output(InstanceId=instance_id, Latest=True)
    while not console_output.get("Output"):
        logging.info("Waiting for console output")
        time.sleep(5)
        console_output = ec2.get_console_output(InstanceId=instance_id, Latest=True)
    # TODO: Make assertions about  the console output
    print(console_output.get("Output"))

    ec2.terminate_instances(InstanceIds=[instance_id])
    ec2.get_waiter("instance_terminated").wait(InstanceIds=[instance_id])


if __name__ == "__main__":
    import argparse
    import logging
    logging.basicConfig(level=logging.INFO)

    parser = argparse.ArgumentParser()
    parser.add_argument("--image-id", required=True)
    parser.add_argument("--region", required=True)
    args = parser.parse_args()

    smoke_test(args.image_id, args.region)