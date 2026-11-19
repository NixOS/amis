import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

from upload_ami import upload_ami
from upload_ami.upload_ami import (
    ImageInfo,
    default_register_image,
    register_image_if_not_exists,
)


def image_info(**fields: Any) -> ImageInfo:
    return cast(
        ImageInfo,
        {
            "file": "/nix/store/image.vhd",
            "label": "26.11",
            "system": "x86_64-linux",
            "boot_mode": "uefi",
            **fields,
        },
    )


def register_image_file(**fields: Any) -> dict[str, Any]:
    """RegisterImage arguments as nixpkgs writes them."""
    return {
        "Architecture": "arm64",
        "BootMode": "uefi",
        "BlockDeviceMappings": [
            {"DeviceName": "/dev/xvda", "Ebs": {"VolumeType": "gp3", "VolumeSize": 4}}
        ],
        "RootDeviceName": "/dev/xvda",
        "VirtualizationType": "hvm",
        "EnaSupport": True,
        "ImdsSupport": "v2.0",
        "SriovNetSupport": "simple",
        **fields,
    }


TAGS = [
    {
        "ResourceType": "image",
        "Tags": [
            {"Key": "Name", "Value": "name"},
            {"Key": "ManagedBy", "Value": "NixOS/amis"},
        ],
    }
]


def fake_ec2(snapshot_gib: int = 3) -> MagicMock:
    ec2 = MagicMock()
    ec2.describe_images.return_value = {"Images": []}
    ec2.describe_snapshots.return_value = {"Snapshots": [{"VolumeSize": snapshot_gib}]}
    ec2.register_image.return_value = {"ImageId": "ami-1"}
    return ec2


def register(register_image: dict[str, Any], snapshot_gib: int = 3) -> dict[str, Any]:
    ec2 = fake_ec2(snapshot_gib)
    register_image_if_not_exists(ec2, "name", register_image, "snap-1", False)
    return cast(dict[str, Any], ec2.register_image.call_args.kwargs)


def root_ebs(request: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], request["BlockDeviceMappings"][0]["Ebs"])


class RegisterImageFile(unittest.TestCase):
    def test_adds_name_snapshot_and_tags(self) -> None:
        expected = register_image_file(
            TpmSupport="v2.0", Name="name", TagSpecifications=TAGS
        )
        root_ebs(expected)["SnapshotId"] = "snap-1"
        self.assertEqual(register(register_image_file(TpmSupport="v2.0")), expected)

    def test_snapshot_on_root_device(self) -> None:
        ephemeral = {"DeviceName": "/dev/sdb", "VirtualName": "ephemeral0"}
        root = {"DeviceName": "/dev/sda1", "Ebs": {"VolumeType": "gp3"}}
        request = register(
            register_image_file(
                RootDeviceName="/dev/sda1", BlockDeviceMappings=[ephemeral, root]
            )
        )
        self.assertEqual(
            request["BlockDeviceMappings"],
            [
                ephemeral,
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {"VolumeType": "gp3", "SnapshotId": "snap-1"},
                },
            ],
        )

    def test_leaves_arguments_unchanged(self) -> None:
        arguments = register_image_file()
        register(arguments)
        self.assertEqual(arguments, register_image_file())

    def test_volume_size_larger_than_snapshot(self) -> None:
        self.assertEqual(
            root_ebs(register(register_image_file(), snapshot_gib=3))["VolumeSize"], 4
        )

    def test_volume_size_smaller_than_snapshot(self) -> None:
        self.assertEqual(
            root_ebs(register(register_image_file(), snapshot_gib=6))["VolumeSize"], 6
        )

    def test_volume_size_absent(self) -> None:
        mappings = [{"DeviceName": "/dev/xvda", "Ebs": {"VolumeType": "gp3"}}]
        ebs = root_ebs(register(register_image_file(BlockDeviceMappings=mappings)))
        self.assertNotIn("VolumeSize", ebs)


class DefaultRegisterImage(unittest.TestCase):
    def test_matches_previous_request(self) -> None:
        request = register(default_register_image(image_info(), enable_tpm=False))
        self.assertEqual(
            request,
            {
                "Name": "name",
                "Architecture": "x86_64",
                "BootMode": "uefi",
                "BlockDeviceMappings": [
                    {
                        "DeviceName": "/dev/xvda",
                        "Ebs": {"SnapshotId": "snap-1", "VolumeType": "gp3"},
                    }
                ],
                "RootDeviceName": "/dev/xvda",
                "VirtualizationType": "hvm",
                "EnaSupport": True,
                "ImdsSupport": "v2.0",
                "SriovNetSupport": "simple",
                "TagSpecifications": TAGS,
            },
        )

    def test_aarch64(self) -> None:
        arguments = default_register_image(
            image_info(system="aarch64-linux"), enable_tpm=False
        )
        self.assertEqual(arguments["Architecture"], "arm64")

    def test_tpm(self) -> None:
        cases = [
            ("x86_64-linux", "uefi", True, True),
            ("x86_64-linux", "uefi", False, False),
            ("x86_64-linux", "uefi-preferred", True, False),
            ("aarch64-linux", "uefi", True, False),
        ]
        for system, boot_mode, enable_tpm, tpm in cases:
            with self.subTest(
                system=system, boot_mode=boot_mode, enable_tpm=enable_tpm
            ):
                arguments = default_register_image(
                    image_info(system=system, boot_mode=boot_mode), enable_tpm
                )
                self.assertEqual("TpmSupport" in arguments, tpm)


class Main(unittest.TestCase):
    def run_main(self, register_image: dict[str, Any] | None) -> MagicMock:
        with tempfile.TemporaryDirectory() as tmp:
            info_file = Path(tmp) / "image-info.json"
            info_file.write_text(json.dumps(image_info()))
            if register_image is not None:
                (Path(tmp) / "register-image.json").write_text(
                    json.dumps(register_image)
                )
            argv = ["upload-ami", "--image-info", str(info_file), "--prefix", ""]
            with (
                patch.object(sys, "argv", argv),
                patch.object(upload_ami, "upload_ami", return_value={}) as upload,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                upload_ami.main()
        return upload

    def test_reads_register_image_file(self) -> None:
        upload = self.run_main(register_image_file())
        self.assertEqual(upload.call_args.args[1], register_image_file())

    def test_without_register_image_file(self) -> None:
        self.assertIsNone(self.run_main(None).call_args.args[1])


class UploadAmi(unittest.TestCase):
    def upload(
        self,
        info: ImageInfo,
        ebs_direct: bool = False,
        register_image: dict[str, Any] | None = None,
    ) -> tuple[MagicMock, MagicMock]:
        with (
            patch("boto3.client", return_value=fake_ec2()),
            patch.object(upload_ami, "import_snapshot_ebs_direct") as ebs,
            patch.object(upload_ami, "import_snapshot_if_not_exist") as s3,
            patch.object(upload_ami, "register_image_if_not_exists") as register,
        ):
            upload_ami.upload_ami(
                info,
                register_image,
                "bucket",
                False,
                "",
                "",
                False,
                [],
                False,
                "vmimport",
                ebs_direct,
            )
        return (ebs if ebs_direct else s3), register

    def test_register_image_file(self) -> None:
        _, register = self.upload(image_info(), register_image=register_image_file())
        self.assertEqual(register.call_args.args[2], register_image_file())

    def test_without_register_image_file(self) -> None:
        _, register = self.upload(image_info())
        self.assertEqual(
            register.call_args.args[2],
            default_register_image(image_info(), enable_tpm=False),
        )

    def test_ebs_direct_format_absent(self) -> None:
        self.upload(image_info(), ebs_direct=True)[0].assert_called_once()

    def test_ebs_direct_raw(self) -> None:
        self.upload(image_info(format="RAW"), ebs_direct=True)[0].assert_called_once()

    def test_ebs_direct_refuses_vhd(self) -> None:
        with self.assertRaises(AssertionError):
            self.upload(image_info(format="VHD"), ebs_direct=True)

    def test_s3_format_absent(self) -> None:
        s3, _ = self.upload(image_info())
        self.assertEqual(s3.call_args.args[5], "VHD")

    def test_s3_raw(self) -> None:
        s3, _ = self.upload(image_info(format="RAW"))
        self.assertEqual(s3.call_args.args[5], "RAW")


if __name__ == "__main__":
    unittest.main()
