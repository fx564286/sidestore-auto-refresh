import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v97", ROOT / "scripts/patch_v97_retained_guest_host_rebind.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

HEADER = "func bringMultitaskViewToFront(uuid: String, from center: CGPoint? = nil) -> Bool {\n    nrgV191AttachGuestWindowHostIfReady()\n"
SAMPLE = HEADER + mod.OLD + "\n}\n"

class GuestHostRebindTests(unittest.TestCase):
    def test_reattaches_same_retained_view_only(self):
        src = mod.patch(SAMPLE)
        self.assertEqual(mod.patch(src), src)
        for token in ("controller.appSceneVC.isAppRunning", "targetView.superview?.window == nil",
                      "controller.parent != nil", "windowHostingView.window",
                      "activationState == .foregroundActive", "windowHostingView.addSubview(targetView)",
                      "nrgV191AttachGuestWindowHostIfReady()", "retained_view_rebound=1"):
            self.assertIn(token,src)
        self.assertNotIn("terminate()", src)
        self.assertNotIn("openAppWindow(",src)
        self.assertNotIn("unregisterMultitaskContainer",src)
        self.assertNotIn("kill(",src)

    def test_still_fails_closed_for_orphan_without_live_controller(self):
        result = mod.patch(SAMPLE)
        self.assertIn('RETURN_FAILED reason=retained_view_has_no_window', result)
        self.assertIn('guard let window = targetView.window else {',result)
        self.assertIn('controller.appSceneVC.isAppRunning',result)

    def test_unexpected_or_duplicate_upstream_is_rejected(self):
        with self.assertRaises(ValueError):
            mod.patch("unrelated text")
        with self.assertRaises(ValueError):
            mod.patch(SAMPLE + mod.OLD)
        with self.assertRaises(ValueError):
            mod.patch(mod.MARKER)

    def test_file_integration_does_not_modify_other_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            target=root/mod.TARGET
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(SAMPLE)
            mod.apply(root)
            first=target.read_text()
            mod.apply(root)
            self.assertEqual(first,target.read_text())

    def test_existing_pinned_dock_anchor(self):
        import os
        base=os.getenv("LIVE_CONTAINER_TEST_SOURCE")
        if base:
            source=(Path(base)/mod.TARGET).read_text()
            self.assertEqual(mod.patch(mod.patch(source)),mod.patch(source))

if __name__=="__main__":
    unittest.main()
