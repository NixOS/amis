import contextlib
import hashlib
import json
import os
from typing import Any
import boto3
import boto3.session
import logging
import botocore.exceptions


class Object(contextlib.AbstractContextManager):
    def __init__(self, bucket: str, key: str, file: str):
        self.key = key
        self.bucket = bucket
        self.object = boto3.resource("s3").Object(bucket, key)  # type: ignore
        logging.info(f"Checking if s3://{bucket}/{key} exists")
        try:
            self.object.load()
        except botocore.exceptions.ClientError as e:
            logging.info(f"Uploading {file} to s3://{bucket}/{key}")
            self.object.upload_file(file)
            self.object.wait_until_exists()

    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool | None:
        logging.info(f"Deleting s3://{self.bucket}/{self.key}")
        self.object.delete()
        return None

    def __dir__(self) -> list[str]:
        return dir(self.object)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.object, name)


class ImportSnapshot(contextlib.AbstractContextManager):
    def __init__(self, s3_object: Object):
        # TODO Also add bucket?
        client_token = hashlib.sha256(s3_object.key.encode()).hexdigest()

        ec2 = boto3.client("ec2")
        logging.info(f"Importing s3://{s3_object.bucket}/{s3_object.key} to EC2")
        snapshot_import_task = ec2.import_snapshot(
            DiskContainer={
                "UserBucket": {"S3Bucket": s3_object.bucket, "S3Key": s3_object.key},
            },
            ClientToken=client_token,
        )
        ec2.get_waiter("snapshot_imported").wait(
            ImportTaskIds=[snapshot_import_task["ImportTaskId"]]
        )
        snapshot_import_tasks = ec2.describe_import_snapshot_tasks(
            ImportTaskIds=[snapshot_import_task["ImportTaskId"]]
        )
        self.snapshot = boto3.resource("ec2").Snapshot(id=snapshot_import_tasks[0]["SnapshotTaskDetail"]["SnapshotId"])  # type: ignore

    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool | None:
        logging.info(f"Deleting snapshot {self.snapshot.id}")
        self.snapshot.delete()

    def __dir__(self) -> list[str]:
        return dir(self.snapshot)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.snapshot, name)


class Image(contextlib.AbstractContextManager):
    def __init__(
        self,
        image_name: str,
        image_info: dict | None = None,
        snapshot: ImportSnapshot | None = None,
    ):
        ec2 = boto3.client("ec2")
        describe_images = ec2.describe_images(
            Owners=["self"], Filters=[{"Name": "name", "Values": [image_name]}]
        )
        if len(describe_images["Images"]) != 0:
            image_id = describe_images["Images"][0]["ImageId"]
        elif image_info is not None and snapshot is not None:
            if image_info["system"] == "x86_64-linux":
                architecture = "x86_64"
            elif image_info["system"] == "aarch64-linux":
                architecture = "arm64"
            else:
                raise Exception("Unknown system: " + image_info["system"])
            logging.info(f"Registering image {image_name} with snapshot {snapshot.id}")
            register_image = ec2.register_image(
                Name=image_name,
                Architecture=architecture,
                BootMode=image_info["boot_mode"],
                BlockDeviceMappings=[
                    {
                        "DeviceName": "/dev/xvda",
                        "Ebs": {
                            "SnapshotId": snapshot.snapshot.id,
                            "VolumeType": "gp3",
                        },
                    }
                ],
                RootDeviceName="/dev/xvda",
                VirtualizationType="hvm",
                EnaSupport=True,
                ImdsSupport="v2.0",
                SriovNetSupport="simple",
                TpmSupport="v2.0" if architecture == "x86_64" else None,
            )
            image_id = register_image["ImageId"]
        else:
            raise Exception("Image not found and no image_info and snapshot provided")
        self.image = boto3.resource("ec2").Image(id=image_id)  # type: ignore

    def __dir__(self) -> list[str]:
        return dir(self.image)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.image, name)

    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool | None:
        logging.info(f"Deregistering image {self.image.id}")
        self.image.deregister()


class Instance(contextlib.AbstractContextManager):
    def __init__(
        self,
        image: Image,
        instance_type: str,
        user_data: str | None = None,
        client_token: str | None = None,
    ):
        hash = hashlib.sha256(image.id.encode())
        hash.update(image.id.encode())
        hash.update(instance_type.encode())
        if user_data is not None:
            hash.update(user_data.encode())
        if client_token is not None:
            hash.update(client_token.encode())
        client_token = hash.hexdigest()
        ec2 = boto3.client("ec2")
        instance = ec2.run_instances(
            ImageId=image.id,
            ClientToken=client_token,
            InstanceType=instance_type,
            UserData=user_data,
            MinCount=1,
            MaxCount=1,
        )
        self.instance = boto3.resource("ec2").Instance(id=instance["Instances"][0]["InstanceId"])  # type: ignore

    def __dir__(self) -> list[str]:
        return dir(self.instance)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.instance, name)

    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool | None:
        logging.info(f"Terminating instance {self.instance.id}")
        self.instance.terminate()


s3_bucket = "images20231124161256194400000001"
revision = "testing"
with open("result/nix-support/image-info.json", "r") as f:
    image_info = json.load(f)
image_name = "nixos-" + image_info["label"] + revision + "-" + image_info["system"]
image_file = image_info["file"]
s3_key = os.path.join(
    os.path.basename(os.path.dirname(image_file)), os.path.basename(image_file)
)
logging.basicConfig(level=logging.INFO)


def run():
    with (
        Object(s3_bucket, s3_key, image_file) as s3_object,
        ImportSnapshot(s3_object) as snapshot,
        Image(image_name, image_info, snapshot) as image,
        # TODO: ClientToken of instance is test code
        Instance(image, "t4g.micro", client_token=__file__) as instance,
    ):
        print(instance.instance.public_ip_address)
        instance.instance.wait_until_running()
        print(instance.console_output(Latest=True))
