"""V28: remote focus/audio scene contract and pinned-source patch regressions."""
import importlib.util
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("LIVE_CONTAINER_TEST_SOURCE", "/shared/nrg-v27-upstream-livecontainer"))

def load_patch():
    path = ROOT / "scripts" / "patch_v28_guest_lifecycle.py"
    spec = importlib.util.spec_from_file_location("v28_guest_lifecycle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class V28GuestLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_patch()

    def make_fixture(self, folder):
        path = Path(folder)
        for name in (self.mod.APP_M, self.mod.APP_H, self.mod.DEC_M,
                     self.mod.DEC_H, self.mod.DOCK):
            src = SOURCE / name
            dst = path / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        return path

    def test_real_pinned_guest_scene_focus_audio_contract(self):
        if not SOURCE.is_dir():
            self.skipTest("Pinned source only available on integration host")
        with tempfile.TemporaryDirectory() as d:
            root = self.make_fixture(d)
            # This test runs twice in CI: on the pristine pinned checkout before
            # integration and on the final generated source after V27 -> V28.
            # Never apply the V28 patch to raw upstream without its V27
            # prerequisites; that was the original #243 CI failure.
            generated = os.environ.get("V28_PATCHED_LIVECONTAINER")
            if not generated:
                self.assertNotIn("NRG_V27_GUEST_SWITCH_LIFECYCLE", (root / self.mod.DOCK).read_text())
                before = [(root / n).read_bytes() for n in (
                    self.mod.APP_M, self.mod.APP_H, self.mod.DEC_M,
                    self.mod.DEC_H, self.mod.DOCK)]
                with self.assertRaisesRegex(SystemExit, "V27 guest lifecycle missing"):
                    self.mod.patch(root)
                after = [(root / n).read_bytes() for n in (
                    self.mod.APP_M, self.mod.APP_H, self.mod.DEC_M,
                    self.mod.DEC_H, self.mod.DOCK)]
                self.assertEqual(before, after, "Pre-patch regression mutated pinned source")
                return
            self.assertEqual(SOURCE.resolve(), Path(generated).resolve(),
                             "Post-patch test must use the actual generated checkout")
            self.mod.patch(root)
            app = (root / self.mod.APP_M).read_text()
            dec = (root / self.mod.DEC_M).read_text()
            dock = (root / self.mod.DOCK).read_text()
            self.assertIn("settings.foreground = foreground;", app)
            self.assertIn("[self.contentView endEditing:YES]", app)
            self.assertIn("[self.appSceneVC lcSetGuestSceneForeground:NO]", dec)
            self.assertIn("self.appSceneVC.contentView endEditing:YES", dec)
            self.assertIn("self.view.transform = CGAffineTransformIdentity;", dec)
            self.assertNotIn("self.view.transform = CGAffineTransformMakeScale(0.1, 0.1)", dec)
            self.assertIn("if (![PiPManager.shared isPiPWithVC:self.appSceneVC])", dec)
            self.assertIn("vc.appSceneVC.contentView?.endEditing(true)", dock)
            self.assertIn("vc.appSceneVC.lcSetGuestSceneForeground(false)", dock)
            self.assertIn("controller?.lcResumeMinimizedGuest()", dock)
            self.assertNotIn("AVAudioSession", dec)
            self.assertNotIn("SIGSTOP", dec)
            before = [(root / n).read_bytes() for n in (self.mod.APP_M, self.mod.APP_H,
                            self.mod.DEC_M, self.mod.DEC_H, self.mod.DOCK)]
            self.mod.patch(root)
            after = [(root / n).read_bytes() for n in (self.mod.APP_M, self.mod.APP_H,
                           self.mod.DEC_M, self.mod.DEC_H, self.mod.DOCK)]
            self.assertEqual(before, after)

    def test_unknown_source_fails_without_partial_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in (self.mod.APP_M, self.mod.APP_H, self.mod.DEC_M,
                         self.mod.DEC_H, self.mod.DOCK):
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("// original source\n")
            with self.assertRaises(SystemExit):
                self.mod.patch(root)
            for name in (self.mod.APP_M, self.mod.APP_H, self.mod.DEC_M,
                         self.mod.DEC_H, self.mod.DOCK):
                self.assertEqual((root / name).read_text(), "// original source\n")

if __name__ == "__main__":
    unittest.main()
