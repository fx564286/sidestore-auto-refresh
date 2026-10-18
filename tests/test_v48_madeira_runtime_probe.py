"""Source-level regression for host-process JIT/Memory diagnostics."""
from pathlib import Path
import importlib.util
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v48_runtime", ROOT/"scripts/patch_v48_madeira_runtime_probe.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)

class MadeiraRuntimeTests(unittest.TestCase):
    def original(self):
        return ("// NRG_V46_JIT_HOST_BUNDLE_RETURN\n"
                + p.INCLUDE_ANCHOR
                + p.FUNCTION_ANCHOR
                + "\nSecTaskCopyValueForEntitlement\n"
                + p.CALL_ANCHOR)

    def test_probe_reports_actual_runtime_not_untrusted_guest_ipa(self):
        out = p.patch(self.original())
        for must in ("nrgV48LogGuestRuntime(\"guest_bootstrap\")", "foreground_after_debugger",
                     "SecTaskCreateFromSelf", "csops(getpid()", "P_TRACED",
                     "get-task-allow", "com.apple.developer.kernel.increased-memory-limit",
                     "com.apple.developer.kernel.extended-virtual-addressing",
                     "jit_pool_unverified=1", "memory_granted=%d"):
            self.assertIn(must, out)
        for never in ("vm_protect(", "vm_allocate(", "AVAudioSession", "beginBackgroundTask",
                      "endEditing:", "SecItemDelete(", "sharedGroup"):
            self.assertNotIn(never, out)
        self.assertEqual(out, p.patch(out))

    def test_no_silent_patching_on_drift(self):
        for bad in ("unexpected upstream", p.FUNCTION_ANCHOR, self.original().replace("NRG_V46_JIT_HOST_BUNDLE_RETURN","old")):
            with self.assertRaises(RuntimeError):
                p.patch(bad)

    def test_no_partial_writes(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / p.TARGET
            file.parent.mkdir(parents=True)
            file.write_text(self.original())
            p.main(Path(temp))
            first = file.read_bytes()
            p.main(Path(temp))
            self.assertEqual(first, file.read_bytes())

if __name__ == "__main__":
    unittest.main()
