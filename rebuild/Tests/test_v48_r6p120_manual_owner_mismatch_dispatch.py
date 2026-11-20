"""R6P120: explicit manual host owner mismatch must reach native guarded installer."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PANEL = (ROOT / 'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
WORKER = (ROOT / 'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text()
AUTO = (ROOT / 'rebuild/HostApp/ScarletAutomaticRenewal.swift').read_text()
WORKFLOW = (ROOT / '.github/workflows/scarlet-paired-engines-build.yml').read_text()
BRANCH = 'fix/scarlet-v48-r6p120-manual-owner-mismatch-20261120'
ASSET = 'Scarlet-Crystal-V48-R6P120-MANUAL-OWNER-MISMATCH-UNSIGNED.ipa'


class R6P120ManualOwnerMismatchDispatch(unittest.TestCase):
    def test_only_explicit_manual_zero_target_owner_mismatch_reaches_existing_worker(self):
        request = PANEL.split('private func requestManualRefresh()', 1)[1].split(
            '// Stage 1: recover', 1)[0]
        self.assertIn('let manuallyOnboardableHost = nativeState.count == 0 &&', request)
        self.assertIn('nativeState.reason == "no_managed_apps_for_selected_team"', request)
        self.assertIn('nativeState.reason == "host_managed_owner_mismatch"', request)
        self.assertIn('nativeState.signingReady', request)
        self.assertIn('guard nativeState.canRefreshSelectedTeam || manuallyOnboardableHost else {', request)
        self.assertIn('ScarletNativeRefreshExecutor.execute(manual: true)', request)
        self.assertNotIn('nativeState.reason == "host_selected_team_mismatch"', request)
        self.assertNotIn('nativeState.reason == "host_managed_record_inactive"', request)

    def test_original_native_worker_retains_cross_owner_native_install_proofs(self):
        manual = WORKER.split('guard !targets.isEmpty else {', 1)[1].split(
            'let signedHostID', 1)[0]
        self.assertIn('if manual, existingReason == nil,', manual)
        self.assertIn('verifiedSameTeamManualHostURL(', manual)
        self.assertIn('ScarletInstallTeamAuthority.hasValidSigningCertificate(', manual)
        self.assertIn('activeSelectedSignerSerial(appleID: selectedAppleID,', manual)
        self.assertIn('ScarletGuestDeviceTransport.ensureReady()', manual)
        self.assertIn('AppManager.shared.install(.url(installedHost)', manual)
        self.assertIn('installed.resignedBundleIdentifier == verifiedHostID', manual)
        self.assertIn('await ScarletInstallTeamAuthority.appBelongsToOwner(', manual)
        self.assertIn('native_host_reinstall_returned_install_unverified', manual)
        self.assertIn('profile.teamIdentifier == teamID', WORKER)

    def test_background_cannot_dispatch_manual_foreign_owner_onboarding(self):
        self.assertIn('guard nativeState.canRefreshSelectedTeam else {', AUTO)
        self.assertIn('ScarletNativeRefreshExecutor.execute()', AUTO)
        self.assertNotIn('execute(manual: true)', AUTO)
        self.assertNotIn('AppManager.shared.install(', AUTO)

    def test_native_release_identity_and_unsigned_publication(self):
        self.assertIn(BRANCH, WORKFLOW)
        self.assertIn('--host-build-version 3.8.120', WORKFLOW)
        self.assertIn('version="3.8.120"', WORKFLOW)
        self.assertIn('asset="' + ASSET + '"', WORKFLOW)
        self.assertIn('asset=' + ASSET, WORKFLOW)
        self.assertIn('tag=scarlet-v48-r6p120-manual-owner-mismatch-unsigned-20261120', WORKFLOW)


if __name__ == '__main__':
    unittest.main()
