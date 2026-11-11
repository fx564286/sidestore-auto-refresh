"""R6.1 audio focus regression checks (source checks, not device playback proof)."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
STACK = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
GLUE = (ROOT / "integration/apply_scarlet_host.py").read_text()
FLOW = (ROOT.parent / ".github/workflows/scarlet-paired-engines-build.yml").read_text()

class GuestAudioHomeFocus(unittest.TestCase):
    def test_home_pauses_each_resident_pid_and_rearms_return(self):
        home = STACK[STACK.index("    func goHome() {"):STACK.index("    private func recoverFastFailedGuest(")]
        self.assertIn("viewport?.pauseAllResidentAudioOnHome()", home)
        audio = STACK[STACK.index("    func pauseAllResidentAudioOnHome() {"):STACK.index("    func select(folder: String)")]
        self.assertIn("vc.pid > 0 && vc.isAppRunning", audio)
        self.assertIn('postGuestAudioScope("pause", pid: vc.pid)', audio)
        self.assertIn("audioScopedPID = 0", audio)
        select = STACK[STACK.index("    func select(folder: String)"):STACK.index("    func reconcile()")]
        self.assertIn('postGuestAudioScope("resume", pid: target.pid)', select)
        self.assertIn("if audioScopedPID != target.pid", select)
        self.assertIn('vc.view.layer.opacity = key == folder ? 1 : 0', select)
        self.assertNotIn("terminate()", home + audio + select)

    def test_log_reports_post_not_ack(self):
        self.assertIn("guest_audio_scope_applied", STACK)
        self.assertIn("posted_not_device_verified", STACK)
        self.assertIn("ScarletGuestAudioPauseCallback", GLUE)
        self.assertIn("ScarletGuestAudioResumeCallback", GLUE)
        self.assertIn("initScarletGuestAudioIsolation", GLUE)

    def test_release_uses_isolated_branch(self):
        self.assertIn("fix/scarlet-v48-r6p1-audio-home-focus-20261111", FLOW)
        self.assertIn("scarlet-v48-r6p1-audio-home-focus-unsigned-20261111", FLOW)
        self.assertIn("Scarlet-Crystal-V48-R6P1-AUDIO-HOME-UNSIGNED.ipa", FLOW)

if __name__ == "__main__":
    unittest.main()
