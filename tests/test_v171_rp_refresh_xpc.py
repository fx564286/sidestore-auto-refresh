import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("v171rp",ROOT/"scripts/patch_v171_rp_refresh_xpc.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class RefreshRPBridge(unittest.TestCase):
    def test_only_typed_reset_is_eligible_and_existing_codec_stays(self):
        src="LC_REFRESH_RESULT_XPC_V1\nfunc reportStructuredRefreshFailure() {}\n"+m.ANCHOR+"\n"+m.OLD
        patched=m.patch(src)
        self.assertEqual(patched,m.patch(patched))
        self.assertEqual(patched.count("SCARLET_V171_RP_FAILURE_XPC"),1)
        self.assertIn('current.domain == NSPOSIXErrorDomain && current.code == 54',patched)
        self.assertIn('current.userInfo["LCStructuredFailureCauseV1"]',patched)
        self.assertIn('current.userInfo["LCStructuredFailureStageV1"]',patched)
        self.assertIn('guard let next = current.userInfo[NSUnderlyingErrorKey]',patched)
        self.assertIn('return error',patched)
        self.assertIn(m.NEW,patched)
        self.assertNotIn('String(describing: error)',patched)
        self.assertNotIn('data.base64EncodedString()',patched)
    def test_fails_closed_on_initial_unspecified_bridge(self):
        with self.assertRaises(ValueError):m.patch("LC_REFRESH_RESULT_XPC_V1\n"+m.OLD)
if __name__=="__main__":unittest.main()
