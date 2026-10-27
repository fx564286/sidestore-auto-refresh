"""Guard against silent changing of the JIT provider on iOS 26/27."""
import importlib.util
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("v135",ROOT/"scripts/patch_v135_restore_jit_provider.py")
v135=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v135)

class V135Tests(unittest.TestCase):
    def test_keep_exact_configured_provider(self):
        source=(ROOT/"scripts/patch_v135_restore_jit_provider.py").read_text()
        self.assertIn("let effectiveEnabler = jitEnabler",source)
        self.assertIn("forced_migration=0",source)
        self.assertNotIn("effectiveEnabler = .StikJIT",v135.app_patch.__doc__ or "")
        self.assertNotIn("LCJITEnablerType\",",source)
        for provider in ("StosDebug", "StikDebug", "LiveProcess", "Classic"):
            self.assertIn(provider,source)
    def test_fail_closed(self):
        for fn in (v135.app_patch,v135.classic_patch):
            with self.assertRaises(ValueError):
                fn("random Swift file")
    def test_combined_134_135_generated(self):
        root=os.environ.get("V135_PATCHED_LIVECONTAINER")
        if not root:return
        root=Path(root)
        app=(root/v135.APP).read_text()
        util=(root/v135.UTIL).read_text()
        self.assertEqual(v135.app_patch(app),app)
        self.assertEqual(v135.classic_patch(util),util)
        self.assertEqual(app.count(v135.MARK),1)
        self.assertIn("SCARLET_V134_JIT_PROTOCOL",app)
        self.assertIn("SCARLET_V134_CLASSIC_JIT_PROTOCOL",util)
        self.assertIn("let effectiveEnabler = jitEnabler",app)
        self.assertIn("let effectiveEnabler = jitEnabler",util)
        self.assertNotIn("effectiveEnabler = .StikJIT",app)
        self.assertNotIn("effectiveEnabler = .StikJIT",util)
        # Still allow the explicit provider via its original branch.
        self.assertIn("if effectiveEnabler == .StosDebug || effectiveEnabler == .StosDebugLC",app)
        self.assertIn("if effectiveEnabler == .StikJITLC",app)
        self.assertIn("effectiveEnabler == .StosDebug || effectiveEnabler == .StosDebugLC",util)
        self.assertIn('"script-name"',util)
        self.assertIn('"script-data"',util)

if __name__=="__main__":unittest.main()
