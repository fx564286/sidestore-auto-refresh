"""V48-R6 contracts for the three user-reported regressions.

1. Experimental resident outside-tap dismissal cannot depend on an ancestor
   UITapGestureRecognizer: a LiveProcess guest surface consumes the touch in
   its own process. The expanded overlay window must stay hit-testable and the
   native shield owns outside hits.
2. The full-bleed resident guest scene has no periphery of its own. Dynamic
   Island / home-indicator guidance belongs only in the safe area, and a
   transient zero top inset must never be written to the guest.
3. Every guest is a separate LiveProcess with its own AVAudioSession. Only the
   visible guest may keep its session active; the host tells the exact PIDs.

Source test only. It is not a claim of real iPhone gesture/optical/audio
verification.
"""
from pathlib import Path
import unittest

R = Path(__file__).resolve().parents[1]
TAB = (R / 'HostApp/ScarletFullscreenGuestTab.swift').read_text()
STACK = (R / 'HostApp/ScarletFullscreenSceneStack.swift').read_text()
GLUE = (R / 'integration/apply_scarlet_host.py').read_text()
W = (R.parent / '.github/workflows/scarlet-paired-engines-build.yml').read_text()


class ResidentThreeIssueRegression(unittest.TestCase):
    def test_outside_tap_uses_expanded_overlay_and_native_shield(self):
        # Expanded overlay is no longer transparent to hit testing outside
        # panelRect. The shield alone rejects panel-internal hits.
        self.assertNotIn('return panelRect.insetBy(dx: -3, dy: -3).contains(point)', TAB)
        self.assertIn('return super.point(inside: point, with: event)', TAB)
        self.assertIn('return !owner.panelRect.insetBy(dx: -3, dy: -3).contains(point)', TAB)
        # Shield tracks rotation/resize and stays above the hosting view.
        self.assertIn('outsideShield?.frame = bounds', TAB)
        self.assertIn('shield.frame = bounds', TAB)
        self.assertIn('bringSubviewToFront(shield)', TAB)
        self.assertIn('dismissState?.requestClose()', TAB)
        self.assertIn('closeGeneration &+= 1', TAB)

    def test_island_inset_is_safe_area_only_and_never_zeroed(self):
        # The resident scene fills the host window: periphery is zero and the
        # safe area alone carries the island inset (initial + remote scene).
        self.assertGreaterEqual(
            GLUE.count('settings.peripheryInsets = UIEdgeInsetsZero;'), 2)
        self.assertIn('settings.safeAreaInsetsPortrait = safe;', GLUE)
        self.assertIn('settings.safeAreaEdgeInsets = safe;', GLUE)
        self.assertNotIn('settings.peripheryInsets = safe;', GLUE)
        # Resolver keeps the host window's positive inset and rejects a
        # transient 0pt top (device log: 62 -> 0 -> 62 within 0.5ms).
        self.assertIn('safe.top = max(safe.top, host.top)', STACK)
        self.assertIn('safe.bottom = max(safe.bottom, host.bottom)', STACK)
        self.assertIn('guest_zero_safe_top_rejected', STACK)
        self.assertIn('previous.top >= 18', STACK)

    def test_guest_audio_is_scoped_to_the_visible_pid(self):
        self.assertIn('private func postGuestAudioScope', STACK)
        self.assertIn('CFNotificationName(name as CFString)', STACK)
        self.assertIn('com.scarlet.guest.audio.', STACK)
        self.assertIn('audioScopedPID != target.pid', STACK)
        self.assertIn('postGuestAudioScope("pause"', STACK)
        self.assertIn('postGuestAudioScope("resume"', STACK)
        self.assertIn('guest_audio_scope_applied', STACK)
        # Guest-side hook lives in the LiveProcess and only deactivates its
        # own session; it never kills or suspends the retained process.
        self.assertIn('SCARLET_GUEST_AUDIO_ISOLATION_V1', GLUE)
        self.assertIn('initScarletGuestAudioIsolation', GLUE)
        self.assertIn('AVAudioSessionSetActiveOptionNotifyOthersOnDeactivation', GLUE)
        self.assertIn('NSUserDefaults.isLiveProcess', GLUE)
        self.assertIn('"guestAudioIsolation": guest_audio', GLUE)
        # Tweaks/ already has LiveContainer/ on its header search path, so the
        # generated file must import "utils.h" like its siblings. The earlier
        # "../LiveContainer/utils.h" resolved to LiveContainer/LiveContainer
        # and failed the real Xcode archive (exit 65).
        self.assertIn('#import "utils.h"', GLUE)
        self.assertNotIn('../LiveContainer/utils.h', GLUE)
        # The hook is linked into a LiveProcess app extension, where
        # UIApplication.sharedApplication is unavailable.
        self.assertNotIn('object:UIApplication.sharedApplication]', GLUE)
        self.assertIn('ScarletUIBecameActiveNotification', GLUE)

    def test_r6_release_branch_and_asset(self):
        self.assertIn('fix/scarlet-v48-r6-island-outside-audio-20261111', W)
        self.assertIn('Scarlet-Crystal-V48-R6-UNSIGNED.ipa', W)
        self.assertIn('scarlet-v48-r6-unsigned-20261111', W)


if __name__ == '__main__':
    unittest.main()
