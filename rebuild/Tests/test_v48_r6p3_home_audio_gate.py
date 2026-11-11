"""R6P3 hidden-resident audio focus regression.

Static/source contract checks; audible routing is verified only by actual
device playback and an iOS log with no post-Home resume.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACK = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()


def between(start, end):
    return STACK.split(start, 1)[1].split(end, 1)[0]


class ResidentHomeAudioGateTests(unittest.TestCase):
    def test_home_hides_before_pausing_all_live_pids(self):
        body = between("    func goHome() {", "    // Some closed-source guests")
        self.assertLess(body.index("isVisible = false"),
                        body.index("viewport?.pauseAllResidentAudioOnHome()"))
        self.assertIn("overlayWindow?.isHidden = true", body)

    def test_hidden_scene_must_never_resume_foreground(self):
        select = between("    func select(folder: String) -> Bool {",
                         "    func reconcile() {")
        self.assertLess(select.index("guard stack?.isVisible == true else { return false }"),
                        select.index('postGuestAudioScope("resume", pid: target.pid)'))
        self.assertLess(select.index("guard stack?.isVisible == true else { return false }"),
                        select.index("target.scarletEnsureRemoteForeground()"))
        self.assertIn("audioScopedPID != target.pid", select)

    def test_reconcile_only_selects_visible_guest(self):
        reconcile = between("    func reconcile() {", "\n}\n\n@available(iOS 17.0, *)\nstruct ScarletFullscreenSceneViewportRepresentable")
        self.assertIn("if stack.isVisible {", reconcile)
        self.assertIn("_ = select(folder: active)", reconcile)
        self.assertIn("home_audio_reactivation_suppressed", reconcile)
        self.assertIn("hiddenAudioReconcileReported = true", reconcile)

    def test_explicit_activation_reveals_before_resuming_audio(self):
        activate = between("    func activate(folder: String) -> Bool {",
                           "    func restoreForegroundOnHostActive()")
        self.assertLess(activate.index("isVisible = true"),
                        activate.index("viewport?.select(folder: folder) == true"))
        self.assertIn("isVisible = wasVisible", activate)
        self.assertIn("activeID = folder", activate)
        self.assertIn("fullscreen_scene_process_reused", activate)

    def test_retained_processes_and_fullscreen_geometry_untouched(self):
        home = between("    func goHome() {", "    // Some closed-source guests")
        select = between("    func select(folder: String) -> Bool {", "    func reconcile() {")
        self.assertNotIn("terminate(", home + select)
        self.assertNotIn("setFrame(", home + select)
        self.assertIn("pauseAllResidentAudioOnHome()", home)


if __name__ == "__main__":
    unittest.main()
