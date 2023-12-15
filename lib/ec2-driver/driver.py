import contextlib
import hashlib
from types import TracebackType
import boto3

ec2client = boto3.client("ec2")
ec2 = boto3.resource("ec2")


class S3Object(contextlib.AbstractContextManager):
    def __init__(self, bucket: str, key: str):
        self.bucket = bucket
        self.key = key

    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool | None:
        return None


class ImportSnapshot(contextlib.AbstractContextManager):
    def __init__(self, s3_object: S3Object):
        self.id = "lol"
        pass

    pass

    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool | None:
        pass


class Image(contextlib.AbstractContextManager):
    def __init__(self, snapshot: ImportSnapshot):
        self.id = "lol"
        pass

    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool | None:
        pass


class Instance(contextlib.AbstractContextManager):
    def __init__(self, image: Image):
        instance_response = ec2client.run_instances(
            ClientToken=image.id,
            ImageId=image.id,
        )
        self.instance = ec2.Instance(instance_response["Instances"][0]["InstanceId"])  # type: ignore
        return self

    def __exit__(self, __exc_type, __exc_value, __traceback) -> bool | None:
        self.instance.terminate()
        return None


def test(instance: Instance):
    pass

with S3Object("bucket", "key") as s3_object, ImportSnapshot(
    s3_object
) as snapshot, Image(snapshot) as image, Instance(image) as instance:
    pass
