import hashlib
import json
import logging
from pathlib import Path
from typing import Iterable, Literal, TypedDict
import boto3
import datetime

from mypy_boto3_ec2.client import EC2Client
from mypy_boto3_ec2.literals import BootModeValuesType
from mypy_boto3_ec2.type_defs import RegionTypeDef, RegisterImageRequestTypeDef

from concurrent.futures import ThreadPoolExecutor

from .snapshot_uploader import upload_snapshot


class ImageInfo(TypedDict):
    file: str
    label: str
    system: str
    boot_mode: BootModeValuesType
    format: str


def import_snapshot_if_not_exist(
    ec2: EC2Client,
    image_name: str,
    image_file: Path,
    region: str,
) -> str:
    """
    Upload a raw disk image directly to an EBS snapshot.

    Idempotent: returns the existing snapshot ID if one with the same
    name tag already exists.
    """
    snapshots = ec2.describe_snapshots(
        OwnerIds=["self"],
        Filters=[
            {"Name": "tag:Name", "Values": [image_name]},
            {"Name": "status", "Values": ["completed"]},
        ],
    )

    if len(snapshots["Snapshots"]) != 0:
        if len(snapshots["Snapshots"]) != 1:
            raise RuntimeError(
                f"Expected 1 snapshot named {image_name!r}, "
                f"found {len(snapshots['Snapshots'])}"
            )
        snapshot_id: str = snapshots["Snapshots"][0]["SnapshotId"]
        return snapshot_id

    client_token = hashlib.sha256(image_name.encode()).hexdigest()
    snapshot_id = upload_snapshot(
        image_file,
        region=region,
        description=image_name,
        tags={"Name": image_name, "ManagedBy": "NixOS/amis"},
        client_token=client_token,
    )
    return snapshot_id


def register_image_if_not_exists(
    ec2: EC2Client,
    image_name: str,
    image_info: ImageInfo,
    snapshot_id: str,
    public: bool,
    enable_tpm: bool,
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

        register_image_kwargs: RegisterImageRequestTypeDef = {
            "Name": image_name,
            "Architecture": architecture,
            "BootMode": image_info["boot_mode"],
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/xvda",
                    "Ebs": {
                        "SnapshotId": snapshot_id,
                        "VolumeType": "gp3",
                    },
                }
            ],
            "RootDeviceName": "/dev/xvda",
            "VirtualizationType": "hvm",
            "EnaSupport": True,
            "ImdsSupport": "v2.0",
            "SriovNetSupport": "simple",
            "TagSpecifications": [
                {
                    "ResourceType": "image",
                    "Tags": [
                        {"Key": "Name", "Value": image_name},
                        {"Key": "ManagedBy", "Value": "NixOS/amis"},
                    ],
                }
            ],
        }

        if (
            enable_tpm
            and architecture == "x86_64"
            and image_info["boot_mode"] == "uefi"
        ):
            register_image_kwargs["TpmSupport"] = "v2.0"

        logging.info(f"Registering image {image_name} with snapshot {snapshot_id}")

        register_image = ec2.register_image(**register_image_kwargs)
        image_id = register_image["ImageId"]

    ec2.get_waiter("image_available").wait(ImageIds=[image_id])
    deprecate_at = (datetime.datetime.now() + datetime.timedelta(days=90)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    logging.info(f"Deprecating {image_id} at {deprecate_at}")
    ec2.enable_image_deprecation(ImageId=image_id, DeprecateAt=deprecate_at)
    if public:
        logging.info(f"Making {image_id} public")
        ec2.modify_image_attribute(
            ImageId=image_id,
            Attribute="launchPermission",
            LaunchPermission={"Add": [{"Group": "all"}]},
        )
    return image_id


def copy_image_to_regions(
    image_id: str,
    image_name: str,
    source_region: str,
    target_regions: Iterable[RegionTypeDef],
    public: bool,
    best_effort_regions: list[str] = [],
) -> dict[str, str]:
    """
    Copy image to all target regions

    Copies to all regions in parallel and waits for all of them to finish

    This function is idempotent because image_id is unique and we use it
    as the client_token for the copy_image task
    """

    def copy_image(
        image_id: str, image_name: str, source_region: str, target_region_name: str
    ) -> tuple[str, str]:
        """
        Copy image to target_region

        This function is idempotent because image_id is unique and we use it as
        the client_token for the copy_image task.

        TODO: How long can we rely on the client_token? E.g. what happens if I rerun this
        script a few months later?

        """
        ec2r: EC2Client = boto3.client("ec2", region_name=target_region_name)
        logging.info(
            f"Copying image {image_id} from {source_region} to {target_region_name}"
        )
        copy_image = ec2r.copy_image(
            SourceImageId=image_id,
            SourceRegion=source_region,
            Name=image_name,
            ClientToken=image_id,
            TagSpecifications=[
                {
                    "ResourceType": "image",
                    "Tags": [
                        {"Key": "Name", "Value": image_name},
                        {"Key": "SourceRegion", "Value": source_region},
                        {"Key": "ManagedBy", "Value": "NixOS/amis"},
                    ],
                },
                {
                    "ResourceType": "snapshot",
                    "Tags": [
                        {"Key": "Name", "Value": image_name},
                        {"Key": "SourceRegion", "Value": source_region},
                        {"Key": "ManagedBy", "Value": "NixOS/amis"},
                    ],
                },
            ],
        )
        ec2r.get_waiter("image_available").wait(ImageIds=[copy_image["ImageId"]])
        logging.info(
            f"Finished image {image_id} from {source_region} to {target_region_name} {copy_image['ImageId']}"
        )
        deprecate_at = (datetime.datetime.now() + datetime.timedelta(days=90)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        logging.info(f"Deprecating {copy_image['ImageId']} at {deprecate_at}")
        ec2r.enable_image_deprecation(
            ImageId=copy_image["ImageId"], DeprecateAt=deprecate_at
        )
        if public:
            logging.info(f"Making {copy_image['ImageId']} public")
            ec2r.modify_image_attribute(
                ImageId=copy_image["ImageId"],
                Attribute="launchPermission",
                LaunchPermission={"Add": [{"Group": "all"}]},
            )
        return (target_region_name, copy_image["ImageId"])

    with ThreadPoolExecutor(max_workers=32) as executor:

        def _copy_image(target_region: RegionTypeDef) -> tuple[str, str] | None:
            assert "RegionName" in target_region
            region_name = target_region["RegionName"]
            try:
                return copy_image(image_id, image_name, source_region, region_name)
            except Exception as e:
                if region_name not in best_effort_regions:
                    logging.error(f"Copying to {region_name} failed: {e}")
                    raise
                logging.warning(
                    f"Copying to {region_name} failed (best-effort, ignoring): {e}"
                )
                return None

        image_ids = dict(
            result
            for result in executor.map(_copy_image, target_regions)
            if result is not None
        )

    image_ids[source_region] = image_id
    return image_ids


def upload_ami(
    image_info: ImageInfo,
    copy_to_regions: bool,
    prefix: str,
    run_id: str,
    public: bool,
    dest_regions: list[str],
    enable_tpm: bool,
    best_effort_regions: list[str] = [],
) -> dict[str, str]:
    """
    Upload NixOS AMI to AWS and return the image ids for each region

    This function is idempotent because all the functions it calls are idempotent.
    """

    ec2: EC2Client = boto3.client("ec2")

    image_file = Path(image_info["file"])
    label = image_info["label"]
    system = image_info["system"]
    image_name = prefix + label + "-" + system + ("." + run_id if run_id else "")

    snapshot_id = import_snapshot_if_not_exist(
        ec2, image_name, image_file, ec2.meta.region_name
    )

    image_id = register_image_if_not_exists(
        ec2, image_name, image_info, snapshot_id, public, enable_tpm
    )

    image_ids: dict[str, str] = {}
    image_ids[ec2.meta.region_name] = image_id

    if copy_to_regions:
        regions = filter(
            lambda x: x.get("RegionName") != ec2.meta.region_name
            and (True if dest_regions == [] else x.get("RegionName") in dest_regions),
            ec2.describe_regions()["Regions"],
        )
        image_ids.update(
            copy_image_to_regions(
                image_id,
                image_name,
                ec2.meta.region_name,
                regions,
                public,
                best_effort_regions,
            )
        )

    return image_ids


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Upload NixOS AMI to AWS")
    parser.add_argument("--image-info", help="Path to image info", required=True)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--copy-to-regions", action="store_true")
    parser.add_argument("--public", action="store_true")
    parser.add_argument(
        "--prefix", required=True, help="Prefix to prepend to image name"
    )
    parser.add_argument("--run-id", help="Run id to append to image name")
    parser.add_argument(
        "--dest-region",
        help="Regions to copy to if copy-to-regions is enabled",
        action="append",
        default=[],
    )
    parser.add_argument(
        "--enable-tpm",
        action="store_true",
        default=False,
        help="Enable TPM 2.0 support for UEFI x86_64 images",
    )
    parser.add_argument(
        "--best-effort-region",
        help="Regions where copy failures are logged as warnings instead of errors",
        action="append",
        default=[],
    )

    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level)

    with open(args.image_info, "r") as f:
        image_info = json.load(f)

    image_ids = upload_ami(
        image_info,
        args.copy_to_regions,
        args.prefix,
        args.run_id,
        args.public,
        args.dest_region,
        args.enable_tpm,
        args.best_effort_region,
    )
    print(json.dumps(image_ids))


if __name__ == "__main__":
    main()
