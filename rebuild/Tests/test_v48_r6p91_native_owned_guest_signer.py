"""P91: native CertificateManager host-team ownership recovery is distinct from P78."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
HOST = ROOT / 'rebuild/HostApp/ScarletIntegratedHostView.swift'
WORKFLOW = ROOT / '.github/workflows/scarlet-paired-engines-build.yml'

class NativeOwnedSignerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.host = HOST.read_text()
        cls.ci = WORKFLOW.read_text()

    def test_recovery_reads_real_native_cert_only_after_legacy_unavailable(self):
        h = self.host
        self.assertIn('trialNativeManagedHostCertificate()', h)
        self.assertIn('retrieveSideStoreCertificate()', h)
        self.assertIn('if nativeCandidate == nil {\n                Task { @MainActor in', h)
        self.assertIn('trialExistingSideStoreCertificate(nativeCandidate:', h)
        self.assertIn('if nativeCandidate == nil {\n        for service in services', h)

    def test_unique_active_owner_and_profile_anchor_allow_same_team_accounts(self):
        h = self.host
        # P93 supersedes P91's Team-count=1 rejection. Two saved IDs may
        # share a Team, but the active owner's P12 must match the host's
        # actual signed embedded profile certificate before any trial.
        self.assertIn('before.filter({ $0.active }).count == 1', h)
        self.assertIn('after.filter({ $0.active }).count == 1', h)
        self.assertNotIn('before.filter({ $0.teamID == hostTeam }).count == 1', h)
        self.assertNotIn('after.filter({ $0.teamID == hostTeam }).count == 1', h)
        self.assertIn('ScarletHostProvisioningSigner.check(', h)
        self.assertIn('after.contains(where: {', h)
        self.assertIn('$0.active && $0.id == owner.id && $0.teamID == hostTeam', h)
        self.assertIn('LCUtils.getCertTeamId(withKeyData: archive,', h)
        self.assertIn('archive != original', h)
        self.assertIn('native_signer_recovery_blocked', h)
        self.assertNotIn('try await ScarletNativeCertificateTransport.shared.obtain()', h)

    def test_existing_crash_safe_reversible_kernel_validation_unchanged(self):
        h = self.host
        for invariant in ('restoreInterruptedTrial()', 'prefs.set(true, forKey: pending)',
                          'prefs.synchronize()', 'LCUtils.validateJITLessSetup { valid, _ in',
                          'restoreOriginal(prefs)', 'signer_recovery_rolled_back',
                          'ScarletGuestSignerRecoveryVerified'):
            self.assertIn(invariant, h)

    def test_independent_build_publish_path(self):
        w = self.ci
        self.assertIn('fix/scarlet-v48-r6p91-native-owned-guest-signer-20261117', w)
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.91)', w)
        self.assertIn('version="3.8.91"', w)
        self.assertIn('Scarlet-Crystal-V48-R6P91-NATIVE-OWNED-SIGNER-UNSIGNED.ipa', w)
        self.assertIn('tag=scarlet-v48-r6p91-native-owned-signer-unsigned-20261117', w)

if __name__ == '__main__':
    unittest.main()
