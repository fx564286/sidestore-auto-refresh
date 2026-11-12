"""R6P26 terminal JSONL field allowlist contract.

The R6P25 iPhone build compiled visible/clipped clipping diagnostics into
LiveProcess and host readBack but emitted none of the four counters:
ScarletDiagnosticRecorder.allowedFields filtered them. Assert full path.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUEST = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
HOST = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
RECORDER = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()

REQUIRED = {
    "visible_unsafe_controls", "clipped_unsafe_controls",
    "visible_unsafe_images", "clipped_unsafe_images",
}


def quoted_keys(body: str):
    return set(re.findall(r'"([a-z_]+)"', body))


def host_geometry_relay_keys():
    source = HOST.split("if result == \"guest_content_geometry_probe\" {", 1)[1]
    numbers = source.split("let numericFields = [", 1)[1].split("]", 1)[0]
    return quoted_keys(numbers)


def recorder_allowlist():
    fields = RECORDER.split("private static let allowedFields: Set<String> = [", 1)[1].split("]", 1)[0]
    return quoted_keys(fields)


class RecorderContract(unittest.TestCase):
    def test_every_guest_geometry_relay_counter_survives_final_jsonl(self):
        relayed = host_geometry_relay_keys()
        allowed = recorder_allowlist()
        self.assertTrue(REQUIRED.issubset(relayed))
        self.assertEqual(relayed - allowed, set(),
                         "Host guest-content geometry relay silently drops JSONL metrics")

    def test_guest_produces_each_counter_and_host_relay_accepts_it(self):
        for key in REQUIRED:
            self.assertIn('@"' + key + '"', GUEST)
            self.assertIn('"' + key + '"', HOST)
            self.assertIn('"' + key + '"', RECORDER)
        self.assertIn('ScarletIslandVisibleFrameInWindow', GUEST)
        self.assertIn('guest_content_geometry_probe', HOST)

    def test_jsonl_field_filter_is_explicit_and_does_not_admit_secrets(self):
        self.assertIn('Self.allowedFields.contains(key)', RECORDER)
        forbidden = {
            'udid', 'apple_id', 'password', 'private_key',
            'profile_data', 'guest_name', 'access_token',
            'file_path', 'raw_url', 'otp',
        }
        self.assertFalse(forbidden.intersection(recorder_allowlist()))
        self.assertEqual(len(REQUIRED), 4)


if __name__ == "__main__":
    unittest.main()
