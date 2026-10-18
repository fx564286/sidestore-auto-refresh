import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("jit",ROOT/"scripts/patch_v47_jit_transport.py")
m=importlib.util.module_from_spec(s)
s.loader.exec_module(m)

class JITTests(unittest.TestCase):
    def test_gateway_fallback_only_and_unverified_status(self):
        src="// NRG_V46_JIT_RECOVERY\n" + m.ANCHOR
        fixed=m.patch(src)
        for code in (502,503,504):
            self.assertIn(f'SideJITServer HTTP {code}',fixed)
        self.assertNotIn('SideJITServer HTTP 401',fixed)
        self.assertIn("try await debugApp(targetBundleId)",fixed)
        self.assertIn("runtime_jit_unverified=1",fixed)
        self.assertNotIn("jit_active=true",fixed)
        self.assertEqual(m.patch(fixed),fixed)
    def test_unexpected_inputs_refused(self):
        with self.assertRaisesRegex(RuntimeError,"requires V46"):
            m.patch(m.ANCHOR)
        with self.assertRaisesRegex(RuntimeError,"anchor count"):
            m.patch("// NRG_V46_JIT_RECOVERY")
if __name__=="__main__": unittest.main()
