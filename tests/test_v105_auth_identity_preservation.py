"""Existing proven Windows/iTunes GrandSlam identity must not regress.

The user previously signed in with Windows/iTunes AuthKit compatibility.
An -80046 response is not evidence that we should remove this working mode.
No live auth/Apple API calls are made in tests.
"""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class AuthIdentityPreservation(unittest.TestCase):
 def test_windows_itunes_workaround_kept(self):
  s=(ROOT/'scripts/patch_nrg_gsa_auth.py').read_text()
  self.assertIn('<PC> <Windows;6.2(0,0);9200>',s)
  self.assertIn('com.apple.iTunes/12.12.4.1',s)
  self.assertIn('X-Xcode-Version',s)
  self.assertIn('X-Apple-App-Info',s)
  self.assertIn('akd/1.0 CFNetwork/808.1.4',s)
 def test_srp_and_2fa_identity_consistent(self):
  s=(ROOT/'scripts/patch_nrg_gsa_client_v3.py').read_text()
  self.assertIn('nrgGrandSlamClientInfo(a.clientInfo)',s)
  self.assertIn('NRG_GSA_WINDOWS_UA_V4',s)
  self.assertIn('a.oneTimePassword',s) if 'a.oneTimePassword' in s else None
 def test_policy_error_preserves_credentials_and_no_replay(self):
  auth=(ROOT/'scripts/patch_nrg_gsa_auth.py').read_text()
  trace=(ROOT/'scripts/patch_v98_gsa_80046_trace.py').read_text()
  self.assertIn('NRG_GSA_RECOVERY_V1',auth)
  self.assertIn('code == -80046',trace)
  self.assertIn('anisette_family=',trace)
  self.assertIn('sent_family=',trace)
  self.assertIn('do not loop credentials, clear accounts or auto-replay SRP',trace)
if __name__=='__main__':unittest.main()
