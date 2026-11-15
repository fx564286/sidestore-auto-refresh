"""P71: real P69 boot pairing race; preserve original SideStore worker guards."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
X=(R/'HostApp/ScarletAuthXPCSupport.swift').read_text()
A=(R/'HostApp/ScarletAutomaticRenewal.swift').read_text()
P=(R/'HostApp/ScarletNativeDevicePairing.swift').read_text()
W=(R/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
class NativePairingBootRace(unittest.TestCase):
 def test_verified_rsd_receipt_bounded_in_memory(self):
  t=X.split('public enum ScarletNativePairingInstaller {')[1].split('public static func install(candidate:')[0]
  for marker in ('private static var lastVerifiedAt: Date?',
                 'private static var inspectionTask:',
                 'Date().timeIntervalSince(at) < 30',
                 'result.1 == "pairing_saved_and_transport_ready"',
                 'return await inspectPersistedState()',
                 'let result = await task.value',
                 'client.scarletInspectDevicePairing',
                 'pairing_state_read_timeout'):
   self.assertIn(marker,t)
  self.assertNotIn('UserDefaults.standard.set(',t)
 def test_auto_refresh_shortcircuits_only_preflight_not_native_worker(self):
  self.assertIn('await ScarletNativePairingInstaller.inspectForAutomaticRefresh()',A)
  self.assertIn('ScarletNativeRefreshInspector.inspect()',A)
  self.assertIn('ScarletNativeRefreshExecutor.execute()',A)
  self.assertIn('ScarletInstalledProfileReadback.beginRequest',A)
  self.assertIn('ensurePostSignInstallTransport()',W)
  self.assertIn('ScarletGuestDeviceTransport.ensureReady()',W)
 def test_transient_timeout_does_not_claim_revocation_or_renewal(self):
  self.assertIn('"보류 · 기기 연결 재확인 예정"',A)
  self.assertIn('pairingReason == "pairing_state_read_timeout"',A)
  self.assertIn('"installation_verified": "false"',A)
  self.assertIn('ScarletNativePairingInstaller.invalidateInspectionHint()',P)
  self.assertIn('invalidateInspectionHint()\n        guard candidate.count',X)
if __name__=='__main__':unittest.main()
