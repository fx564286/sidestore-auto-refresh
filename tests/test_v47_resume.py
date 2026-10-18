"""V47 host lifecycle restoration: pinned-safe, guest-specific, no audio hijack."""
from pathlib import Path
import importlib.util
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v47_resume", ROOT/"scripts/patch_v47_resume.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class ResumeTests(unittest.TestCase):
    def test_dock_restores_only_visible_guest(self):
        src = "// NRG_V46_GUEST_KEYBOARD_SCOPE\n// NRG_V28_GUEST_LIFECYCLE\n// lcResumeMinimizedGuest\n" + mod.DOCK_ANCHOR
        fixed = mod.patch_dock(src)
        self.assertIn("view.window?.windowScene === hostScene", fixed)
        self.assertIn("view.alpha > 0.1", fixed)
        self.assertIn("controller.appSceneVC.isAppRunning", fixed)
        self.assertIn("controller.lcResumeMinimizedGuest()", fixed)
        self.assertIn("PiPManager.shared?.isPiP", fixed)
        self.assertNotIn("setActive:YES", fixed)
        self.assertNotIn("AVAudioSession.sharedInstance", fixed)
        self.assertNotIn("window.endEditing(true)", fixed)
        self.assertNotIn("becomeFirstResponder", fixed)
        self.assertEqual(mod.patch_dock(fixed), fixed)

    def test_app_delegate_observes_actual_activation(self):
        original = mod.DELEGATE_ANCHOR
        fixed = mod.patch_delegate(original)
        self.assertIn("func sceneDidBecomeActive(_ scene: UIScene)", fixed)
        self.assertIn("nrgV47RestoreVisibleGuestScenes", fixed)
        self.assertNotIn("sceneWillEnterForeground", fixed)
        self.assertEqual(mod.patch_delegate(fixed), fixed)

    def test_fails_closed_without_earlier_lifecycle(self):
        with self.assertRaisesRegex(RuntimeError, "requires existing guest lifecycle"):
            mod.patch_dock(mod.DOCK_ANCHOR)
        with self.assertRaisesRegex(RuntimeError, "expected one anchor"):
            mod.patch_delegate("unrecognized upstream")

    def test_atomic_preflight_and_idempotence(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for rel in (mod.DOCK, mod.DELEGATE):
                (root/rel).parent.mkdir(parents=True, exist_ok=True)
            (root/mod.DOCK).write_text("// V46 missing\n" + mod.DOCK_ANCHOR)
            (root/mod.DELEGATE).write_text(mod.DELEGATE_ANCHOR)
            with self.assertRaisesRegex(RuntimeError, "requires existing"):
                mod.main(root)
            self.assertEqual((root/mod.DELEGATE).read_text(), mod.DELEGATE_ANCHOR)
            (root/mod.DOCK).write_text("// NRG_V46_GUEST_KEYBOARD_SCOPE\n// NRG_V28_GUEST_LIFECYCLE\n// lcResumeMinimizedGuest\n" + mod.DOCK_ANCHOR)
            mod.main(root)
            first = [(root/rel).read_bytes() for rel in (mod.DOCK, mod.DELEGATE)]
            mod.main(root)
            self.assertEqual(first, [(root/rel).read_bytes() for rel in (mod.DOCK, mod.DELEGATE)])

if __name__ == "__main__":
    unittest.main()
