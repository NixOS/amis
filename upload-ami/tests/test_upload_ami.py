import unittest
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

from upload_ami import upload_ami
from upload_ami.upload_ami import ImageInfo, register_image_if_not_exists


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


def fake_ec2(snapshot_gib: int = 3) -> MagicMock:
    ec2 = MagicMock()
    ec2.describe_images.return_value = {"Images": []}
    ec2.describe_snapshots.return_value = {"Snapshots": [{"VolumeSize": snapshot_gib}]}
    ec2.register_image.return_value = {"ImageId": "ami-1"}
    return ec2


def register(
    info: ImageInfo, snapshot_gib: int = 3, enable_tpm: bool = False
) -> dict[str, Any]:
    ec2 = fake_ec2(snapshot_gib)
    register_image_if_not_exists(ec2, "name", info, "snap-1", False, enable_tpm)
    return cast(dict[str, Any], ec2.register_image.call_args.kwargs)


class RootVolumeSize(unittest.TestCase):
    def test_absent(self) -> None:
        ebs = register(image_info())["BlockDeviceMappings"][0]["Ebs"]
        self.assertNotIn("VolumeSize", ebs)

    def test_larger_than_snapshot(self) -> None:
        ebs = register(image_info(root_volume_size_gib=4), snapshot_gib=3)[
            "BlockDeviceMappings"
        ][0]["Ebs"]
        self.assertEqual(ebs["VolumeSize"], 4)

    def test_smaller_than_snapshot(self) -> None:
        ebs = register(image_info(root_volume_size_gib=4), snapshot_gib=6)[
            "BlockDeviceMappings"
        ][0]["Ebs"]
        self.assertEqual(ebs["VolumeSize"], 6)


class TpmSupport(unittest.TestCase):
    def test_absent_without_flag(self) -> None:
        self.assertNotIn("TpmSupport", register(image_info()))

    def test_absent_with_flag(self) -> None:
        for system in ("x86_64-linux", "aarch64-linux"):
            with self.subTest(system=system):
                kwargs = register(image_info(system=system), enable_tpm=True)
                self.assertEqual(kwargs["TpmSupport"], "v2.0")

    def test_absent_with_flag_without_uefi(self) -> None:
        info = image_info(boot_mode="uefi-preferred")
        self.assertNotIn("TpmSupport", register(info, enable_tpm=True))

    def test_true(self) -> None:
        kwargs = register(image_info(tpm_support=True))
        self.assertEqual(kwargs["TpmSupport"], "v2.0")

    def test_false_overrides_flag(self) -> None:
        kwargs = register(image_info(tpm_support=False), enable_tpm=True)
        self.assertNotIn("TpmSupport", kwargs)


class Format(unittest.TestCase):
    def upload(self, info: ImageInfo, ebs_direct: bool) -> MagicMock:
        with (
            patch("boto3.client", return_value=fake_ec2()),
            patch.object(upload_ami, "import_snapshot_ebs_direct") as ebs,
            patch.object(upload_ami, "import_snapshot_if_not_exist") as s3,
            patch.object(upload_ami, "register_image_if_not_exists"),
        ):
            upload_ami.upload_ami(
                info, "bucket", False, "", "", False, [], False, "vmimport", ebs_direct
            )
        return ebs if ebs_direct else s3

    def test_ebs_direct_absent(self) -> None:
        self.upload(image_info(), ebs_direct=True).assert_called_once()

    def test_ebs_direct_raw(self) -> None:
        self.upload(image_info(format="RAW"), ebs_direct=True).assert_called_once()

    def test_ebs_direct_refuses_vhd(self) -> None:
        with self.assertRaises(AssertionError):
            self.upload(image_info(format="VHD"), ebs_direct=True)

    def test_s3_absent(self) -> None:
        s3 = self.upload(image_info(), ebs_direct=False)
        self.assertEqual(s3.call_args.args[5], "VHD")

    def test_s3_raw(self) -> None:
        s3 = self.upload(image_info(format="RAW"), ebs_direct=False)
        self.assertEqual(s3.call_args.args[5], "RAW")


if __name__ == "__main__":
    unittest.main()
