import importlib.util, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("v171rp",ROOT/"scripts/patch_v171_rp_refresh_xpc.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class RefreshRPBridge(unittest.TestCase):
    def test_only_typed_evidence_and_run_identity(self):
        src="LC_REFRESH_RESULT_XPC_V1\n"+m.ANCHOR+"\n"+m.OLD
        patched=m.patch(src)
        self.assertEqual(patched,m.patch(patched))
        self.assertIn('UUID(uuidString: runID) != nil',patched)
        self.assertIn('native.domain == NSPOSIXErrorDomain && native.code == 54',patched)
        self.assertIn('native.userInfo["LCStructuredFailureCauseV1"]',patched)
        self.assertIn('native.userInfo["LCStructuredFailureStageV1"]',patched)
        self.assertIn('"operation": "refresh", "stage": "pairing"',patched)
        self.assertIn('"retryable": false',patched)
        self.assertIn('fromPropertyList: wire, format: .binary',patched)
        self.assertIn(m.NEW,patched)
        self.assertNotIn('String(describing: error)',patched)
        self.assertNotIn('error.userInfo.description',patched)
    def test_fails_closed(self):
        with self.assertRaises(ValueError):m.patch("LC_REFRESH_RESULT_XPC_V1\n"+m.OLD)
if __name__=="__main__":unittest.main()
