"""P78: actual failed JIT-less signer cannot be repaired by mere P12 existence."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
P=HOST.split('// R6P78_SIGNER_SELF_RECOVERY_BEGIN',1)[1].split('// R6P78_SIGNER_SELF_RECOVERY_END',1)[0]
class NativeSignerRecovery(unittest.TestCase):
 def test_real_jitless_postcheck_only_and_original_p12_backup(self):
  for x in ('if category == "signature_postcheck_invalid"',
            'ScarletGuestSignerRecovery.trialExistingSideStoreCertificate()',
            'let original = LCUtils.certificateData()',
            'let originalPassword = LCSharedUtils.certificatePassword()',
            'guard readiness.canAttemptLocalGuestSignerRecovery else {',
            'prefs.set(original, forKey: backupCert)',
            'prefs.set(originalPassword, forKey: backupPassword)',
            'prefs.set(true, forKey: pending)',
            'guard prefs.synchronize() else',
            'LCUtils.validateJITLessSetup { valid, _ in'):
   self.assertIn(x,HOST,x)
 def test_ios17_native_recovery_availability_contract(self):
  self.assertIn('@available(iOS 17.0, *)\n@MainActor\nenum ScarletGuestSignerRecovery {',HOST)
  self.assertIn('guard readiness.canAttemptLocalGuestSignerRecovery else {',P)
 def test_actual_team_is_signed_host_not_active_account_b(self):
  for x in ('SecTaskCopyValueForEntitlement(',
    'com.apple.developer.team-identifier',
    'LCUtils.getCertTeamId(withKeyData: candidate,',
    'password: password) == signedHostTeam',
    'candidate != original',
    'kSecAttrAccount as String: "signingCertificate"',
    'kSecAttrAccount as String: "signingCertificatePassword"'):
   self.assertIn(x,P,x)
  self.assertNotIn('SecItemDelete(',P);self.assertNotIn('CertificateManager.shared.revoke',P)
 def test_crash_safe_rollback_and_concurrent_user_choice(self):
  for x in ('static func restoreInterruptedTrial()',
    'let restored = restoreOriginal(prefs)',
    'prefs.set(cert, forKey: certKey)',
    'prefs.set(password, forKey: passwordKey)',
    'LCSharedUtils.certificatePassword() == password',
    'private static let candidateFingerprint',
    'SHA256.hash(data: data)',
    'digest(current) != expected',
    'clearBackup(prefs)',
    'guard prefs.data(forKey: certKey) == candidate else',
    'if success {',
    '"kernel_signature_postcheck_passed"',
    '"original_p12_preserved"'):
   self.assertIn(x,P,x)
 def test_guest_launch_gate_and_boot_recovery_order(self):
  appearance=HOST.split('.onAppear {',1)[1]
  self.assertLess(appearance.index('ScarletGuestSignerRecovery.restoreInterruptedTrial()'),
                  appearance.index('ScarletGuestSessionLedger.prepareForHostAppearance()'))
  self.assertIn('guard !ScarletGuestSignerRecovery.active &&',HOST)
  self.assertIn('"signer_recovery_validation_in_progress"',HOST)
  self.assertIn('ScarletGuestSignerRecoveryVerified',HOST)
 def test_new_release(self):
  for x in ('fix/scarlet-v48-r6p78-signer-recovery-20261116',
             '--host-build-version 3.8.78', '"r6p78"',
             'Scarlet-Crystal-V48-R6P78-SIGNER-RECOVERY-UNSIGNED.ipa',
             'scarlet-v48-r6p78-signer-recovery-unsigned-20261116'):
   self.assertIn(x,W,x)
if __name__=='__main__': unittest.main()
