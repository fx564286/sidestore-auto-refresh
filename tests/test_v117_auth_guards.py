"""V117 regression: effective GSA identity and bounded Keychain diagnostics.

Source integrity only; the existing V116 Swift harness executes the actual
client-profile selection and negative fallback case on the macOS CI runner.
No authentication, provisioning or Keychain writes are attempted by this test.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class V117AuthGuards(unittest.TestCase):
    def test_fallback_user_agent_is_selected_before_legacy_mac(self):
        source = (ROOT / "scripts/patch_v116_sideinstaller_gsa.py").read_text(
            encoding="utf-8"
        )
        compat = source.index("if nrgGrandSlamUsesWindowsCompatibility(original) {")
        legacy = source.index("if nrgGSAIsLegacyMac(original) {", compat)
        self.assertLess(compat, legacy)
        self.assertIn('return "akd/1.0 CFNetwork/808.1.4"', source)
        self.assertIn('nrgGrandSlamClientInfo(anisetteData.clientInfo)', source)
        self.assertIn('nrgGrandSlamClientInfo(a.clientInfo)', source)

    def test_keychain_snapshot_logging_records_status_transitions(self):
        source = (ROOT / "scripts/templates/embedded_shared_keychain.swift").read_text(
            encoding="utf-8"
        )
        start = source.index("    private static let snapshotLogLock = NSLock()")
        end = source.index("    static func authenticationFailure(", start)
        logger = source[start:end]
        self.assertIn("lastSnapshotStatus: Int? = nil", logger)
        self.assertIn("let shouldLog = lastSnapshotStatus != status", logger)
        self.assertIn("lastSnapshotStatus = status", logger)
        self.assertIn("snapshotLogLock.lock()", logger)
        self.assertIn("snapshotLogLock.unlock()", logger)
        self.assertIn("guard shouldLog else { return }", logger)
        self.assertNotIn("snapshotSuccessLogged", logger)
        self.assertNotIn("status != 0 ||", logger)

    def test_no_credential_replay_or_signout_added_by_v117(self):
        profile = (ROOT / "scripts/patch_v116_sideinstaller_gsa.py").read_text(
            encoding="utf-8"
        )
        header_logic = profile.split("LEGACY_MAC_HELPER = r'''", 1)[1].split("'''", 1)[0]
        for forbidden in (
            "signOut(", "SecItemDelete(", "adiPb =", "resetAnisette(",
            "verificationCode(", "authenticate(", "appleIDPassword",
        ):
            self.assertNotIn(forbidden, header_logic)


if __name__ == "__main__":
    unittest.main()
