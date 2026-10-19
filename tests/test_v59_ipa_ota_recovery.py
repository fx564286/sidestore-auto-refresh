import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def source(name):
    return (ROOT / name).read_text(encoding="utf-8")

class V59IPAOTARecoveryTests(unittest.TestCase):
    def test_ota_staging_allows_unlisted_externally_installed_host(self):
        patch = source("scripts/patch_v57_ota_identity.py")
        self.assertIn("NRG_V59_OTA_EXTERNAL_INSTALL", patch)
        self.assertNotIn("reason=installed_host_not_matched count=%d", patch)
        self.assertIn("note = hostEntry == nil", patch)
        self.assertIn("current > 0, !signedHostID.isEmpty", patch)
        self.assertIn("await status.reloadAndWait(manual: true)", patch)
        self.assertIn("hostEntry.bundleID == signedHostID", patch)
    def test_invalid_package_recovery(self):
        policy = source("scripts/templates/v3_behavioral_primitives.swift")
        self.assertIn("NRG_V59_IPA_RECOVERY", policy)
        self.assertIn("not a GitHub Actions artifact ZIP", policy)
    def test_parser_preserves_diagnostic_type_without_private_path(self):
        for name in ("scripts/templates/v3_headless_runtime.swift",
                     "scripts/templates/v3_ipa_staging.swift"):
            code = source(name)
            self.assertIn("[NRG_V59_IPA] phase=", code)
            self.assertIn("error_type=%@ error_domain=%@ error_code=%ld", code)
            self.assertNotIn('NSLog("[NRG_V59_IPA] path=', code)

if __name__ == "__main__":
    unittest.main()
