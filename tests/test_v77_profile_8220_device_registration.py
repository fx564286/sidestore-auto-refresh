import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("v77", ROOT / "scripts/patch_v77_profile_8220_device_registration.py")
v77 = importlib.util.module_from_spec(s)
s.loader.exec_module(v77)

class DeviceProfileTests(unittest.TestCase):
    def test_pinned_source_transform(self):
        source = "LC_PROVISIONING_PARENT_ID_UPSTREAM_V1\n" + v77.ANCHOR
        result = v77.patch(source)
        self.assertEqual(result, v77.patch(result))
        self.assertIn("serverCode == 8220", result)
        self.assertIn("fetchDevices(for: team, types: .all)", result)
        self.assertIn("identifier: udid", result)
        self.assertEqual(result.count("registerDevice("), 1)
    def test_unknown_revision_rejected(self):
        with self.assertRaises(ValueError):
            v77.patch("no expected pinned anchor")
    def test_portal_recovery_is_specific(self):
        source=(ROOT / "scripts/templates/combined_failure.swift").read_text()
        self.assertIn('signingContext["server_code"] == "8220"',source)

if __name__ == "__main__":
    unittest.main()
