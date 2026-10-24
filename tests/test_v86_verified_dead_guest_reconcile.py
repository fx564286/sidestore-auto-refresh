"""V86: end only kernel-confirmed stale registrations; never kill live guests."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(filename: str, tag: str):
    spec = importlib.util.spec_from_file_location(tag, ROOT / "scripts" / filename)
    out = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(out)
    return out

v86 = module("patch_v86_verified_dead_guest_reconcile.py", "v86")
v75 = module("patch_v75_retained_guest_reconcile.py", "v75")


class VerifiedDeadGuestTests(unittest.TestCase):
    def test_manager_tracks_real_positive_pid_and_exits_only_esrch(self):
        out = v86.patch_manager("enum MultitaskMode : Int { case virtualWindow = 0 }\n"
                                 + "class Dummy {\n" + v86.ORIGINAL_MANAGER + "}\n")
        self.assertEqual(v86.patch_manager(out), out)
        self.assertIn(v86.MARKER, out)
        self.assertIn("import Darwin", out)
        self.assertIn("getpgid(pid_t(owner))", out)
        self.assertIn("processGroup == -1 && errno == ESRCH", out)
        self.assertIn("let owner = guestOwnerPID[container], owner > 0", out)
        self.assertIn("if !usingMultitaskContainers.contains(container)", out)
        self.assertNotIn("SIGKILL", out)
        self.assertNotIn("kill(", out)

    def test_scene_captures_pid_before_registration(self):
        before = "header\n" + v86.ORIGINAL_SCENE + "footer"
        out = v86.patch_scene(before)
        self.assertEqual(v86.patch_scene(out), out)
        self.assertLess(out.index("self.pid = [self.extension pidForRequestIdentifier"),
                        out.index("registerMultitaskContainerWithContainer:self.dataUUID pid:self.pid"))
        self.assertNotIn("registerMultitaskContainerWithContainer:self.dataUUID];", out)

    def test_v75_retry_and_failclosed_retained_owner_survive(self):
        source = v75.patch("header\n"+v75.OLD+"\nfooter")
        out = v86.patch_model(source)
        self.assertEqual(v86.patch_model(out), out)
        self.assertIn("for delayNs in [UInt64(180_000_000), 350_000_000, 550_000_000]", out)
        self.assertIn("if stillOwned && !deadOwnerReleased {", out)
        self.assertIn("safe_to_cold_launch=0", out)
        self.assertIn("reconcileVerifiedDeadContainer(container: currentDataFolder)", out)
        self.assertIn("verified_dead_owner_cleared", out)
        self.assertNotIn("forceQuit", out)
        self.assertNotIn("SIGKILL", out)

    def test_partial_install_or_unknown_upstream_rejected(self):
        with self.assertRaises(ValueError):
            v86.patch_manager("MultitaskManager.swift without pinned methods")
        with self.assertRaises(ValueError):
            v86.patch_scene("unknown object")
        with self.assertRaises(ValueError):
            v86.patch_model(v86.ORIGINAL_MODEL)
        with self.assertRaises(ValueError):
            v86.patch_manager(v86.MARKER)

    def test_transaction_fails_without_writing_other_two_files(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root)
            for file in (v86.MANAGER, v86.SCENE, v86.MODEL):
                (base/file).parent.mkdir(parents=True, exist_ok=True)
            (base/v86.MANAGER).write_text(v86.ORIGINAL_MANAGER)
            (base/v86.SCENE).write_text(v86.ORIGINAL_SCENE)
            (base/v86.MODEL).write_text("not V75")
            with self.assertRaises(ValueError):
                v86.apply(base)
            self.assertEqual((base/v86.MANAGER).read_text(),v86.ORIGINAL_MANAGER)
            self.assertEqual((base/v86.SCENE).read_text(),v86.ORIGINAL_SCENE)

    def test_integration_replay_against_available_pinned_source(self):
        import os
        root = os.getenv("LIVE_CONTAINER_TEST_SOURCE")
        if not root or os.getenv("V86_PATCHED_LIVECONTAINER") != "1":
            return
        for relative, fn in ((v86.MANAGER,v86.patch_manager),
                             (v86.SCENE,v86.patch_scene),
                             (v86.MODEL,v86.patch_model)):
            current = (Path(root)/relative).read_text()
            self.assertEqual(fn(current),current)


if __name__ == "__main__":
    unittest.main()
