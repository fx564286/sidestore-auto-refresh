"""R6 opt-in scope contract; unit checks do not prove iPhone sound or pixels."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCENE = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
INTEGRATION = (ROOT / "integration/apply_scarlet_host.py").read_text()
RECORDER = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()
WORKFLOW = (ROOT.parent / ".github/workflows/scarlet-paired-engines-build.yml").read_text()


class R6AudioAndDrawability(unittest.TestCase):
    def test_audio_focus_pid_specific_no_host_session_mutation(self):
        self.assertIn('com.kdt.scarlet.audiofocus.', SCENE)
        self.assertIn('notify_post($0)', SCENE)
        self.assertIn('selectedFolder == folder', SCENE)
        self.assertIn('vc.pid > 0, vc.isAppRunning', SCENE)
        self.assertIn('posted_not_device_verified', SCENE)
        self.assertIn('synchronizeGuestAudioFocus(selectedFolder: nil)', SCENE)
        self.assertIn('lastAudioFocusRequests.removeValue', SCENE)
        self.assertNotIn('AVAudioSession.sharedInstance()', SCENE)

    def test_guest_only_liveprocess_audio_receiver_and_voice_exemption(self):
        self.assertIn('def install_pilot_audio_focus_in_liveprocess(', INTEGRATION)
        self.assertIn('engine / "LiveProcess/main.m"', INTEGRATION)
        self.assertIn("SCPilotRegisterAudioFocus();", INTEGRATION)
        self.assertIn('notify_register_dispatch(', INTEGRATION)
        self.assertIn('if(!playback)', INTEGRATION)  # call and recording categories are intentionally excluded
        self.assertIn('AVAudioSessionCategoryPlayback', INTEGRATION)
        self.assertIn('AVAudioSessionCategoryAmbient', INTEGRATION)
        self.assertIn('AVAudioSessionCategorySoloAmbient', INTEGRATION)
        self.assertIn('non_playback_category_preserved', INTEGRATION)
        self.assertIn('SCPilotAudioSuppressed', INTEGRATION)
        self.assertIn('hasSuffix:@".app"', INTEGRATION)
        self.assertIn('deviceAudioResultVerified": False', INTEGRATION)

    def test_hidden_layers_do_not_disable_remote_compositor(self):
        self.assertIn('view.insertSubview(vc.view, belowSubview: visibleGuest.view)', SCENE)
        self.assertIn('vc.view.layer.opacity = 1', SCENE)
        self.assertNotIn('vc.view.layer.opacity = key == folder ? 1 : 0', SCENE)
        self.assertNotIn('vc.view.layer.opacity = 0', SCENE)
        self.assertIn('vc.view.isUserInteractionEnabled = key == folder', SCENE)
        self.assertIn('target.scarletRemoteContentReady()', SCENE)
        self.assertIn('if stack.isVisible, let active = stack.activeID', SCENE)

    def test_attached_does_not_claim_rendered(self):
        self.assertIn('fullscreen_scene_presenter_attached', SCENE)
        self.assertIn('content_ready_visibility_not_verified', SCENE)
        self.assertNotIn('fullscreen_scene_first_surface_revealed', SCENE)

    def test_signing_and_native_pan_not_modified(self):
        self.assertIn('classicFallbackAttempted: Set<String>', SCENE)
        self.assertIn('scarletEnsureRemoteForeground()', SCENE)
        self.assertNotIn('removeApp(', SCENE)
        self.assertNotIn('LCSharedUtils.revoke', SCENE)
        self.assertIn('original_pan_used', RECORDER)

    def test_r6_ci_isolated_release(self):
        self.assertIn('fix/scarlet-v48-r6-audio-scene-focus-20261111', WORKFLOW)
        self.assertIn('scarlet-v48-r6-audio-scene-focus-unsigned-20261111', WORKFLOW)
        self.assertIn('Scarlet-Crystal-V48-R6-AUDIO-FOCUS-UNSIGNED.ipa', WORKFLOW)


if __name__ == "__main__":
    unittest.main()
