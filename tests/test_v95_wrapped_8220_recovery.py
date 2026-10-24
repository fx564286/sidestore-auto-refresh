"""V95 regression: typed 8220 is preserved through the portal NSError boundary.

Review target: original Source ServerError->lcStructuredSigningFailure->
V77 FetchProvisioningProfiles operation. This test does not contact Apple or
assert that registration/retry will necessarily succeed on the real device.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v77 = load("scripts/patch_v77_profile_8220_device_registration.py", "v77_v95")


class Wrapped8220Tests(unittest.TestCase):
    def setUp(self):
        self.generated = v77.patch("import Foundation\nLC_PROVISIONING_PARENT_ID_UPSTREAM_V1\n" + v77.ANCHOR)

    def test_both_typed_and_request_scoped_wrapped_8220_are_handled(self):
        source = self.generated
        for text in (
            "catch {",
            "SCARLET_V95_WRAPPED_8220",
            "error as? ServerError",
            "serverCode == 8220",
            'wrapped.userInfo["LCStructuredSigningContextV1"]',
            'wrapped.userInfo["LCStructuredFailureSourceV1"]',
            'source == "provisioningProfileRetrieval"',
            'facts?["typed_error"] == "sideSignServerReportedError"',
            'facts?["server_code"] == "8220"',
            "guard typed8220 else { throw error }",
        ):
            self.assertIn(text, source)

    def test_recovery_stays_bounded_to_real_device_and_one_retry(self):
        source = self.generated
        self.assertEqual(source.count("downloadProvisioningProfile("), 2)
        self.assertEqual(source.count("registerDevice("), 1)
        self.assertIn("fetchUDID()", source)
        self.assertIn("fetchDevices(for: team, types: .all)", source)
        self.assertIn("try Task.checkCancellation()", source)
        self.assertNotIn("deleteAppID", source)
        self.assertNotIn("deleteProvisioningProfile", source)
        self.assertEqual(v77.patch(source), source)

    def test_verified_refresh_label_must_not_use_attempt_date(self):
        scheduler = (ROOT / "scripts/templates/livecontainer_refresh_scheduler.swift").read_text()
        shell = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text()
        self.assertIn('defaults.set(Date(), forKey: lastSuccessfulKey)', scheduler)
        after = shell.split("    private func refreshVerificationRow() {", 1)[1].split("    func recordFailure(", 1)[0]
        self.assertIn("SCARLET_V95_VERIFIED_REFRESH_ONLY", after)
        self.assertIn('liveContainerAutoRefreshLastSuccessfulRefresh', after)
        self.assertNotIn('manifest["date"]', after)

if __name__ == "__main__":
    unittest.main()
