"""V49 source-level regression tests."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v49", ROOT / "scripts/patch_v49_auto_jit.py")
v49 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v49)

class V49AutoJITTests(unittest.TestCase):
    def get_source(self):
        override = os.environ.get("LIVE_CONTAINER_TEST_SOURCE")
        options = [Path(override) if override else None, ROOT / "work/LiveContainer"]
        for d in options:
            if d is not None and (d / v49.PATH).exists():
                return (d / v49.PATH).read_text()
        self.skipTest("Pinned LiveContainer source not present")

    def test_patch_source_idempotent(self):
        result = v49.patch(self.get_source())
        self.assertEqual(v49.patch(result), result)
        for term in ("NRG_V49_VERIFIED_AUTO_RESUME", "nrgV49CSOps(getpid(), 0",
                     "(flags & 0x10000000) != 0", "jitAlert.show && nrgV49HostIsDebugged()",
                     "for _ in 0..<360", "verifiedReturn.cancel()", "URLComponents()",
                     'URLQueryItem(name: "pid"', 'URLQueryItem(name: "script-data"',
                     "runtime_jit_unverified=1"):
            self.assertIn(term, result)
        self.assertNotIn("if true {", result)

    def test_fail_closed_on_unexpected_source(self):
        with self.assertRaises(RuntimeError):
            v49.patch("import Foundation\n")

    def test_patch_does_not_touch_user_data_or_signing(self):
        result = v49.patch(self.get_source())
        for token in ("SecItemDelete(", "ideviceinstaller", "uninstall", "mobileprovision",
                      "LCOrignalBundleIdentifier ="):
            self.assertNotIn(token, result)
        self.assertIn("Guest JIT pool is not yet verified", result)

    def test_patch_no_partial_write_on_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / v49.PATH
            path.parent.mkdir(parents=True)
            path.write_text("broken source")
            with self.assertRaises(RuntimeError):
                v49.main(Path(temp))
            self.assertEqual(path.read_text(), "broken source")

if __name__ == "__main__":
    unittest.main()
