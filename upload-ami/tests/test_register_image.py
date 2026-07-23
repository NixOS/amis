"""Tests for build_register_image_request()."""

import unittest
from typing import Any, cast

from upload_ami.upload_ami import RegisterImageInfo, build_register_image_request


def _valid_register_image() -> dict[str, Any]:
    """Return a minimal valid registerImage as a plain dict for easy mutation in tests."""
    return {
        "Architecture": "x86_64",
        "BootMode": "legacy-bios",
        "RootDeviceName": "/dev/xvda",
        "VirtualizationType": "hvm",
        "EnaSupport": True,
        "ImdsSupport": "v2.0",
        "SriovNetSupport": "simple",
        "TpmSupport": None,
        "BlockDeviceMappings": [
            {
                "DeviceName": "/dev/xvda",
                "Ebs": {"VolumeType": "gp3"},
            }
        ],
    }


def _build(image_name: str, ri: dict[str, Any], snapshot_id: str) -> dict[str, Any]:
    """Wrapper that casts the plain dict to RegisterImageInfo for mypy."""
    return dict(
        build_register_image_request(
            image_name, cast(RegisterImageInfo, ri), snapshot_id
        )
    )


class TestBuildRegisterImageRequest(unittest.TestCase):
    def test_valid_input(self) -> None:
        result = _build("test-image", _valid_register_image(), "snap-123")
        self.assertEqual(result["Name"], "test-image")
        self.assertEqual(result["Architecture"], "x86_64")
        self.assertEqual(result["BootMode"], "legacy-bios")
        self.assertEqual(
            result["BlockDeviceMappings"][0]["Ebs"]["SnapshotId"], "snap-123"
        )
        self.assertEqual(result["BlockDeviceMappings"][0]["Ebs"]["VolumeType"], "gp3")
        self.assertNotIn("TpmSupport", result)

    def test_tpm_included_when_set(self) -> None:
        ri = _valid_register_image()
        ri["TpmSupport"] = "v2.0"
        result = _build("test-image", ri, "snap-123")
        self.assertEqual(result["TpmSupport"], "v2.0")

    def test_missing_required_field(self) -> None:
        for field in (
            "Architecture",
            "BootMode",
            "RootDeviceName",
            "BlockDeviceMappings",
            "VirtualizationType",
            "EnaSupport",
            "ImdsSupport",
            "SriovNetSupport",
        ):
            ri = _valid_register_image()
            del ri[field]
            with self.assertRaises(ValueError, msg=f"missing {field}") as ctx:
                _build("img", ri, "snap-1")
            self.assertIn(field, str(ctx.exception))

    def test_forbidden_name(self) -> None:
        ri = _valid_register_image()
        ri["Name"] = "sneaky"
        with self.assertRaises(ValueError) as ctx:
            _build("img", ri, "snap-1")
        self.assertIn("Name", str(ctx.exception))

    def test_forbidden_tag_specifications(self) -> None:
        ri = _valid_register_image()
        ri["TagSpecifications"] = []
        with self.assertRaises(ValueError) as ctx:
            _build("img", ri, "snap-1")
        self.assertIn("TagSpecifications", str(ctx.exception))

    def test_multiple_mappings(self) -> None:
        ri = _valid_register_image()
        ri["BlockDeviceMappings"].append(
            {"DeviceName": "/dev/sdb", "Ebs": {"VolumeType": "gp3"}}
        )
        with self.assertRaises(ValueError) as ctx:
            _build("img", ri, "snap-1")
        self.assertIn("exactly one", str(ctx.exception))

    def test_missing_device_name(self) -> None:
        ri = _valid_register_image()
        del ri["BlockDeviceMappings"][0]["DeviceName"]
        with self.assertRaises(ValueError) as ctx:
            _build("img", ri, "snap-1")
        self.assertIn("DeviceName", str(ctx.exception))

    def test_missing_ebs(self) -> None:
        ri = _valid_register_image()
        del ri["BlockDeviceMappings"][0]["Ebs"]
        with self.assertRaises(ValueError) as ctx:
            _build("img", ri, "snap-1")
        self.assertIn("Ebs", str(ctx.exception))

    def test_missing_volume_type(self) -> None:
        ri = _valid_register_image()
        del ri["BlockDeviceMappings"][0]["Ebs"]["VolumeType"]
        with self.assertRaises(ValueError) as ctx:
            _build("img", ri, "snap-1")
        self.assertIn("VolumeType", str(ctx.exception))

    def test_device_name_mismatch(self) -> None:
        ri = _valid_register_image()
        ri["BlockDeviceMappings"][0]["DeviceName"] = "/dev/sda1"
        with self.assertRaises(ValueError) as ctx:
            _build("img", ri, "snap-1")
        self.assertIn("does not match", str(ctx.exception))

    def test_preset_snapshot_id(self) -> None:
        ri = _valid_register_image()
        ri["BlockDeviceMappings"][0]["Ebs"]["SnapshotId"] = "snap-bad"
        with self.assertRaises(ValueError) as ctx:
            _build("img", ri, "snap-1")
        self.assertIn("SnapshotId", str(ctx.exception))

    def test_arm64_uefi(self) -> None:
        ri = _valid_register_image()
        ri["Architecture"] = "arm64"
        ri["BootMode"] = "uefi"
        result = _build("arm-img", ri, "snap-456")
        self.assertEqual(result["Architecture"], "arm64")
        self.assertEqual(result["BootMode"], "uefi")


if __name__ == "__main__":
    unittest.main()
