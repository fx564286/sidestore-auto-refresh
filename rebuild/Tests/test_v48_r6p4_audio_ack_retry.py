"""R6P4: guest AVAudioSession receipt and retry source-contract regressions.
Receipt confirms the guest's setActive result, not acoustic silence.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
GLUE = (ROOT / "integration/apply_scarlet_host.py").read_text()

class GuestAudioAckTests(unittest.TestCase):
    def test_guest_emits_scoped_receipt_after_setactive(self):
        self.assertIn("com.scarlet.guest.audio.ack.%@.%@.%d", GLUE)
        self.assertIn("ScarletGuestAudioReceipt(NO, result)", GLUE)
        self.assertIn("ScarletGuestAudioReceipt(YES, result)", GLUE)
        self.assertIn("getpid()", GLUE)

    def test_pause_result_is_checked_and_retried_in_same_process(self):
        body = GLUE.split("static void ScarletGuestAudioRetryPause(int attempt) {")[1].split("static void ScarletGuestAudioApply(BOOL active) {")[0]
        self.assertIn("BOOL result = [AVAudioSession.sharedInstance setActive:NO", body)
        self.assertIn("if(!result && attempt < 2)", body)
        self.assertIn("if(scarletGuestAudioPaused) ScarletGuestAudioRetryPause(attempt + 1)", body)
        self.assertIn("dispatch_get_main_queue()", body)
        self.assertNotIn("terminate", body)

    def test_repeated_pause_reasserts_deactivation(self):
        body = GLUE.split("static void ScarletGuestAudioApply(BOOL active) {")[1].split("static void ScarletGuestAudioPauseCallback(")[0]
        self.assertIn("ScarletGuestAudioRetryPause(0);", body)
        self.assertIn("if(!scarletGuestAudioPaused) {", body)
        self.assertNotIn("if(scarletGuestAudioPaused == !active) return;", body)

    def test_host_subscribes_before_guest_command(self):
        body = HOST.split("private func postGuestAudioScope(_ action: String, pid: Int32) {")[1].split("func pauseAllResidentAudioOnHome()")[0]
        self.assertLess(body.index("ScarletGuestAudioReceiptObserver.shared.observe(pid: pid)"),
                        body.index("CFNotificationCenterPostNotification("))
        self.assertIn("guest_audio_device_receipt", HOST)
        self.assertIn('"scope": "av_audio_session_set_active"', HOST)
        self.assertIn("posted_not_device_verified", HOST)

    def test_home_audio_gate_preserved(self):
        select = HOST.split("    func select(folder: String) -> Bool {")[1].split("    func reconcile() {")[0]
        self.assertIn("guard stack?.isVisible == true else { return false }", select)
        self.assertIn('postGuestAudioScope("resume", pid: target.pid)', select)

if __name__ == "__main__":
    unittest.main()
