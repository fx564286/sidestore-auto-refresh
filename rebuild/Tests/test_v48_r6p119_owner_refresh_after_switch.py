"""R6P119 verified-account refresh recovery and prior-profile re-sign input."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = (ROOT / "rebuild/integration/apply_scarlet_host.py").read_text()
WORKER = (ROOT / "rebuild/integration/ScarletGuestRefreshAgent.swift.txt").read_text()
AUTO = (ROOT / "rebuild/HostApp/ScarletAutomaticRenewal.swift").read_text()
WORKFLOW = (ROOT / ".github/workflows/scarlet-paired-engines-build.yml").read_text()

class R6P119OwnerRefresh(unittest.TestCase):
    def test_verified_switch_after_certificate_readback_triggers_catchup(self):
        f = INTEGRATION.split('private func scarletSwitchToSavedAccount(', 1)[1]
        verified = f.split('"settings_account_switch_verified", status: "success")', 1)[1]
        self.assertIn('await scarletEnsureCertificateForActiveAccount()', verified)
        self.assertIn('if scarletAccountSwitchError == nil', verified)
        self.assertIn('await ScarletAutomaticRenewal.shared.refreshAfterVerifiedAccountSwitch()', verified)
        self.assertLess(verified.index('await scarletEnsureCertificateForActiveAccount()'),
                        verified.index('refreshAfterVerifiedAccountSwitch()'))
        self.assertNotIn('refreshAfterVerifiedAccountSwitch()', f.split(
            '"settings_account_switch_verified", status: "success")', 1)[0])

    def test_only_explicit_owner_switch_bypasses_stale_attempt_cooldown(self):
        self.assertIn('func refreshAfterVerifiedAccountSwitch() async', AUTO)
        self.assertIn('refreshIfDue(origin: "verified_account_switch")', AUTO)
        self.assertIn('if origin != "verified_account_switch",', AUTO)
        self.assertIn('guard !running else { return false }', AUTO)
        self.assertIn('guard nativeState.canRefreshSelectedTeam else {', AUTO)
        self.assertIn('ScarletNativeRefreshExecutor.execute()', AUTO)

    def test_expired_old_host_is_source_but_new_certificate_is_authority(self):
        f = WORKER.split('private func performRegistration(', 1)[1].split(
            '\n}\n\n// P102:', 1)[0]
        self.assertNotIn('profile.expirationDate > Date()', f)
        self.assertIn('let profile = signedHost.provisioningProfile else', f)
        self.assertIn('profile.teamIdentifier == owner.teamID', f)
        self.assertIn('ownerSigner.x509.expiryDate > Date()', f)
        self.assertIn('signedOwnerProven', f)

    def test_legacy_original_id_requires_exact_signed_id_and_unique_owner(self):
        f = WORKER.split('private func performRegistration(', 1)[1].split(
            '\n}\n\n// P102:', 1)[0]
        self.assertIn('existing.bundleIdentifier == bundleID', f)
        self.assertIn('bundleID == "com.kdt.livecontainer.P8EZT3U5N4." + currentTeamID', f)
        self.assertIn('guard signedOwnerProven, existing.isActive,', f)
        self.assertIn('hostRows.count <= 1', f)
        self.assertIn('oldExtensionIDs == signedExtensionIDs', f)
        self.assertNotIn('SecItemDelete(', f)
        self.assertNotIn('revokeCertificate(', f)
        self.assertNotIn('AppManager.shared.install(', f)

    def test_unique_native_identity_and_public_asset(self):
        branch='fix/scarlet-v48-r6p119-owner-refresh-20261120'
        asset='Scarlet-Crystal-V48-R6P119-OWNER-REFRESH-UNSIGNED.ipa'
        self.assertIn(branch, WORKFLOW)
        self.assertIn('--host-build-version 3.8.119', WORKFLOW)
        self.assertIn('version="3.8.119"', WORKFLOW)
        self.assertIn('asset="'+asset+'"', WORKFLOW)
        self.assertIn('asset='+asset, WORKFLOW)
        self.assertIn('tag=scarlet-v48-r6p119-owner-refresh-unsigned-20261120', WORKFLOW)

if __name__ == '__main__':
    unittest.main()
