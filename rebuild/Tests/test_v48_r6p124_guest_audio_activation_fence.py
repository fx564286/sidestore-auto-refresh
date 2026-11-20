"""R6P124: a paused LiveProcess cannot reactivate audio by itself."""
from pathlib import Path
import unittest
import re

ROOT = Path(__file__).resolve().parents[1]
PATCHER = (ROOT / "integration/apply_scarlet_host.py").read_text()
HOST = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
WORKFLOW = (ROOT.parent / ".github/workflows/scarlet-paired-engines-build.yml").read_text()


class GuestAudioActivationFenceTests(unittest.TestCase):
    def test_guest_only_fence_registration_and_atomic_state(self):
        self.assertIn('if(!NSUserDefaults.isLiveProcess) return;', PATCHER)
        self.assertIn('static atomic_bool scarletGuestAudioActivationFenced = ATOMIC_VAR_INIT(false);', PATCHER)
        self.assertIn('ScarletGuestAudioInstallActivationFence();', PATCHER)
        self.assertRegex(PATCHER, r'atomic_store_explicit\(&scarletGuestAudioActivationFenced,\s*true,\s*memory_order_release\)')
        self.assertRegex(PATCHER, r'atomic_store_explicit\(&scarletGuestAudioActivationFenced,\s*false,\s*memory_order_release\)')

    def test_sync_and_async_activation_cannot_bypass_paused_fence(self):
        for marker in ('ScarletGuestAudioGuardedSetActive(',
                       'ScarletGuestAudioGuardedSetActiveWithOptions(',
                       'ScarletGuestAudioGuardedActivateAsync('):
            self.assertIn(marker, PATCHER)
        for selector in ('@selector(setActive:error:)',
                         '@selector(setActive:withOptions:error:)',
                         '@"activateWithOptions:completionHandler:"'):
            self.assertIn(selector, PATCHER)
        self.assertGreaterEqual(
            len(re.findall(r'atomic_load_explicit\(&scarletGuestAudioActivationFenced,\s*memory_order_acquire\)', PATCHER)), 3)
        self.assertIn('AVAudioSessionErrorCodeCannotStartPlaying', PATCHER)
        self.assertIn('ScarletGuestAudioReceiptBlocked()', PATCHER)

    def test_generated_objc_fence_error_has_declared_sdk_compatible_domain(self):
        # Xcode 27.2 does not declare AVAudioSessionErrorDomain as an ObjC
        # identifier. This error is synthetic, not an OS session error.
        self.assertIn('errorWithDomain:@"com.scarlet.guest.audio.focus"', PATCHER)
        self.assertNotIn('errorWithDomain:AVAudioSessionErrorDomain', PATCHER)
        self.assertIn('code:AVAudioSessionErrorCodeCannotStartPlaying', PATCHER)

    def test_fence_reports_but_does_not_change_earlier_pause_contract(self):
        self.assertIn('ScarletGuestAudioRetryPause(0);', PATCHER)
        self.assertIn('ScarletGuestAudioReceipt(NO, result);', PATCHER)
        self.assertIn('for outcome in ["ok", "error", "blocked"]', HOST)
        self.assertIn('"scope": "av_audio_session_set_active"', HOST)
        self.assertNotIn('AVAudioSession.sharedInstance.setCategory', HOST)
        self.assertIn('for (key, vc) in controllers where key != folder {', HOST)
        self.assertIn('postGuestAudioScope("pause", pid: vc.pid)', HOST)

    def test_new_ipa_identity_keeps_r6p123_label_change_in_ancestry(self):
        branch = 'fix/scarlet-v48-r6p124-guest-audio-focus-20261121'
        self.assertIn(branch, WORKFLOW)
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.124)', WORKFLOW)
        self.assertIn('Scarlet-Crystal-V48-R6P124-GUEST-AUDIO-FOCUS-UNSIGNED.ipa', WORKFLOW)
        self.assertIn('scarlet-v48-r6p124-guest-audio-focus-unsigned-20261121', WORKFLOW)
        self.assertIn('Text("선택한 계정의 SideStore 관리 앱 목록")',
                      (ROOT / 'Sources/ScarletIndependentUI/ScarletIndependentShell.swift').read_text())


if __name__ == '__main__':
    unittest.main()
