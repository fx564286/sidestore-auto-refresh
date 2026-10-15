import pathlib
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
class GSAWindowsIdentityTest(unittest.TestCase):
    def test_known_good_windows_headers_and_stage_logging(self):
        auth=(ROOT/"scripts/patch_nrg_gsa_auth.py").read_text()
        twofa=(ROOT/"scripts/patch_nrg_gsa_client_v3.py").read_text()
        transport=(ROOT/"scripts/patch_nrg_gsa_http_v2.py").read_text()
        self.assertIn("<PC> <Windows;6.2(0,0);9200>",auth)
        self.assertNotIn('return "<Pixel 7>',auth)
        self.assertIn('X-Xcode-Version',auth)
        self.assertIn('com.apple.gs.xcode.auth',auth)
        self.assertIn('akd/1.0 CFNetwork/808.1.4',auth)
        self.assertIn('NRG_GSA_WINDOWS_UA_V4',twofa)
        self.assertIn('akd/1.0 CFNetwork/808.1.4',twofa)
        self.assertIn('NRG_GSA_STEP_TRACE_V4',transport)
        self.assertIn('["init", "complete", "apptokens"]',transport)
if __name__=="__main__":
    unittest.main()
