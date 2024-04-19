import argparse
import json
import logging
from re import I
import boto3
import subprocess
from typing import Literal, TypedDict
from mypy_boto3_ec2 import EC2Client
from mypy_boto3_ec2.literals import BootModeValuesType


class ImageInfo(TypedDict):
    file: str
    label: str
    system: str
    boot_mode: BootModeValuesType
    format: str


def register_image_if_not_exists(
    ec2: EC2Client,
    image_name: str,
    image_info: ImageInfo,
    snapshot_id: str,
    public: bool,
) -> str:
    """
    Register image if it doesn't exist yet

    This function is idempotent because image_name is unique
    """
    describe_images = ec2.describe_images(
        Owners=["self"], Filters=[{"Name": "name", "Values": [image_name]}]
    )
    if len(describe_images["Images"]) != 0:
        assert len(describe_images["Images"]) == 1
        assert "ImageId" in describe_images["Images"][0]
        image_id = describe_images["Images"][0]["ImageId"]
    else:
        architecture: Literal["x86_64", "arm64"]
        assert "system" in image_info
        if image_info["system"] == "x86_64-linux":
            architecture = "x86_64"
        elif image_info["system"] == "aarch64-linux":
            architecture = "arm64"
        else:
            raise Exception("Unknown system: " + image_info["system"])

        logging.info(f"Registering image {image_name} with snapshot {snapshot_id}")

        # TODO(arianvp): Not all instance types support TPM 2.0 yet. We should
        # upload two images, one with and one without TPM 2.0 support.

        # if architecture == "x86_64" and image_info["boot_mode"] == "uefi":
        #    tpmsupport['TpmSupport'] = "v2.0"

        register_image = ec2.register_image(
            Name=image_name,
            Architecture=architecture,
            BootMode=image_info["boot_mode"],
            BlockDeviceMappings=[
                {
                    "DeviceName": "/dev/xvda",
                    "Ebs": {
                        "SnapshotId": snapshot_id,
                        "VolumeType": "gp3",
                    },
                }
            ],
            RootDeviceName="/dev/xvda",
            VirtualizationType="hvm",
            EnaSupport=True,
            ImdsSupport="v2.0",
            SriovNetSupport="simple",
        )
        image_id = register_image["ImageId"]

    ec2.get_waiter("image_available").wait(ImageIds=[image_id])
    if public:
        logging.info(f"Making {image_id} public")
        ec2.modify_image_attribute(
            ImageId=image_id,
            Attribute="launchPermission",
            LaunchPermission={"Add": [{"Group": "all"}]},
        )
    return image_id


def upload_coldsnap(
    *,
    image_info: ImageInfo,
    prefix: str,
) -> str:
    logging.info(f"Uploading image to coldsnap")

    snapshot_id = str(
        subprocess.check_output(
            [
                "coldsnap",
                "upload",
                "--wait",
            ]
        )
    )

    ec2 = boto3.client("ec2")
    image_name = prefix + image_info["label"] + "-" + image_info["system"]

    image_id = register_image_if_not_exists(
        ec2=ec2,
        image_name=image_name,
        image_info=image_info,
        snapshot_id=snapshot_id,
        public=False,
    )
    return image_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image-info", help="Path to image info", required=True)
    parser.add_argument("--prefix", help="Prefix for image name", required=True)
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()

    if args.debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(level=level)

    image_info: ImageInfo
    with open(args.image_info) as f:
        image_info = json.load(f)

    print(
        upload_coldsnap(
            image_info=args.image_info,
            prefix=args.prefix,
        )
    )
