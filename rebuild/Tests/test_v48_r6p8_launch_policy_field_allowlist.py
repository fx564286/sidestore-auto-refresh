"""R6P8: regression for an observed, device-confirmed R6P7 log bug.

The iPhone report (R6P7 SourceCommit 2d16d43d) contained eight
launch_policy.guest_bundle_policy_observed records for PIDs 957,959,961,968
and zero guest/host policy keys. The raw guest payload was captured, but the
host's ScarletDiagnosticRecorder.allowedFields discarded all those keys.

This test targets that exact data-loss path, not the unverified UI cause.
"""
import unittest
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
REC = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()
LED = (ROOT / "HostApp/ScarletGuestSessionLedger.swift").read_text()
GLUE = (ROOT / "integration/apply_scarlet_host.py").read_text()
STACK = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()

class DevicePolicyRelay(unittest.TestCase):
    expected = [
        "host_status_hidden", "guest_status_hidden",
        "actual_status_hidden", "cf_status_hidden",
        "host_controller_status", "guest_controller_status",
        "actual_controller_status", "host_fullscreen",
        "guest_fullscreen", "actual_fullscreen",
        "host_scene_manifest", "guest_scene_manifest",
        "actual_scene_manifest", "host_orientations",
        "guest_orientations", "actual_orientations"
    ]

    def test_every_guest_policy_key_survives_host_privacy_allowlist(self):
        # Extract real Set literal, not arbitrary references in documentation.
        allowlist = REC.split("private static let allowedFields: Set<String> = [", 1)[1].split("\n    ]", 1)[0]
        allowed = set(re.findall(r'"([a-z_]+)"', allowlist))
        for key in self.expected:
            with self.subTest(key=key):
                self.assertIn(key, allowed)
                self.assertIn('"' + key + '"', LED)
                self.assertIn('@"' + key + '"', GLUE)
        self.assertIn("policy_only", allowed)
        self.assertIn("policy_fields_received", allowed)
        self.assertIn("policy_fields_persisted", allowed)

    def test_report_reflects_policy_field_loss_not_false_success(self):
        self.assertIn('fields["policy_fields_received"] = String(received)', LED)
        self.assertIn('fields["policy_fields_persisted"] = String(persisted)', LED)
        self.assertIn('status: persisted == allowed.count ? "success" : "warning"', LED)
        self.assertIn("count + ((row[key] as? NSNumber) == nil ? 0 : 1)", LED)
        self.assertIn("count + (fields[key] == nil ? 0 : 1)", LED)

    def test_original_guest_runtime_and_geometry_untouched(self):
        self.assertIn("ScarletGuestLaunchPolicySnapshot", GLUE)
        self.assertIn("overwriteMainNSBundle(appBundle);", GLUE)
        self.assertIn("overwriteMainCFBundle();", GLUE)
        self.assertIn("guest_audio_device_receipt", STACK)
        self.assertIn("home_audio_reactivation_suppressed", STACK)
        self.assertIn("fullscreen_scene_direct_switch", STACK)

    def test_privacy_controls_remain(self):
        self.assertIn("guard Self.allowedFields.contains(key) else { return nil }", REC)
        self.assertIn("return (key, Self.sanitized(value))", REC)
        self.assertIn("return \"[REDACTED]\"", REC)
        self.assertIn("if n >= -1 && n <= 20", LED)
        self.assertIn("epoch >= currentStart", LED)

if __name__ == "__main__":
    unittest.main()
