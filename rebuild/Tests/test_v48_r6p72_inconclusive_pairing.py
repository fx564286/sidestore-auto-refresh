"""P72: a timed-out redundant pairing read is NOT a real worker failure."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
A=(R/'HostApp/ScarletAutomaticRenewal.swift').read_text()
W=(R/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
FLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class NativePairingTimeoutFailOpenOnlyToRealWorker(unittest.TestCase):
 def test_only_timeout_may_proceed_past_redundant_preflight(self):
  block=A.split('let (paired, pairingReason) =',1)[1].split('// Login and LC P12 were insufficient',1)[0]
  self.assertIn('!paired &&\n            pairingReason == "pairing_state_read_timeout"',block)
  self.assertIn('guard paired || pairingProbeInconclusive else {',block)
  self.assertIn('"automatic_pairing_preflight_inconclusive"',block)
  self.assertIn('"installation_verified": "false"',block)
  for reason in ('pairing_saved_transport_unavailable','transport_unavailable'):
   self.assertIn(reason,block)
 def test_original_postsign_transport_still_enforces_pairing(self):
  after=A.split('guard paired || pairingProbeInconclusive else {',1)[1]
  for code in ('ScarletNativeRefreshInspector.inspect()',
               'guard nativeState.canRefreshSelectedTeam else {',
               'ScarletNativeRefreshExecutor.execute()',
               'ScarletInstalledProfileReadback.beginRequest(source: "automatic")'):
   self.assertIn(code,after)
  self.assertIn('ensurePostSignInstallTransport()',W)
  self.assertIn('ensureRPPairingReady()',W)
  self.assertIn('fetchUDID(forceLive: true)',W)
 def test_new_build_has_independent_versioned_release(self):
  for s in ('fix/scarlet-v48-r6p72-native-pairing-recheck-20261115',
            '--host-build-version 3.8.72',
            'Scarlet-Crystal-V48-R6P72-NATIVE-PAIRING-RECHECK-UNSIGNED.ipa',
            'scarlet-v48-r6p72-native-pairing-recheck-unsigned-20261115'):
   self.assertIn(s,FLOW)
if __name__=='__main__':unittest.main()
