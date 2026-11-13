"""P49 native key-host status bar scheme contract (device result is separate)."""
import unittest
from pathlib import Path
P=Path(__file__).resolve().parents[1]
STACK=(P/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
HOST=(P/'HostApp/ScarletIntegratedHostView.swift').read_text()
GUEST=(P/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
WF=(P.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class P49KeyHostStatusBar(unittest.TestCase):
    def test_true_key_scene_prefers_guest_tone(self):
        body=STACK.split('func syncKeyHostStatusBarTone(',1)[1].split('func restoreForegroundOnHostActive()',1)[0]
        self.assertIn('guard isVisible, let activeID,',body)
        self.assertIn('slots.contains(where:',body)
        self.assertIn('let next: ColorScheme? = tone == 1 ? .light : (tone == 2 ? .dark : nil)',body)
        self.assertIn('hostStatusBarScheme = next',body)
        self.assertIn('scene.windows.contains(where: { $0.isKeyWindow })',body)
        self.assertIn('resident_key_host_status_bar_readback',body)
        # P52 observed palette regression: the old global appearance request is withdrawn.
        self.assertIn('unforced_host_status_style_mismatch_guest',body)
        self.assertIn('scene.statusBarManager?.statusBarStyle.rawValue',body)
        self.assertNotIn('windowLevel =',body)
        self.assertNotIn('UIStatusBarStyleLightContent',body)

    def test_historical_root_preference_withdrawn_after_p52_palette_regression(self):
        # P49's key-window tone request changed unrelated host settings
        # colors. Keep its passive readback and P51 collision suppression,
        # but never publish the guest theme as a global presentation style.
        self.assertNotIn('.preferredColorScheme(',HOST)
        self.assertIn('guest_tone_read_only_original_palette_preserved',STACK)
        # P51 signed-device video proves unconditional native icons
        # collide with guest top actions. The host leaves Home visible and
        # gates the guest-only status bar on measured risk.
        self.assertIn('.statusBarHidden(fullscreenStack.isVisible &&', HOST)
        self.assertIn('hostStatusBarScheme = nil',STACK.split('func goHome()',1)[1].split('private func recoverFastFailedGuest',1)[0])
        self.assertIn('hostStatusBarScheme = nil',STACK.split('func enqueueSignedGuest(',1)[1].split('func attach(',1)[0])
        self.assertIn('syncKeyHostStatusBarForActiveGuest()',STACK.split('func activate(folder:',1)[1].split('func syncKeyHostStatusBarTone',1)[0])
        self.assertIn('stack?.syncKeyHostStatusBarTone(pid: pid, tone: tone, scene: scene)',STACK)

    def test_only_native_system_icons_and_unchanged_fullscreen_guest(self):
        self.assertNotIn('UILabel(text: "battery',STACK)
        self.assertNotIn('UIDevice.current.batteryLevel',STACK)
        self.assertIn('let top = reserved ? chromeTop(in: scene) : 0',STACK)
        self.assertIn('chromeFreshUnsafeProofPIDs.contains(pid)',STACK)
        self.assertIn('overlay.windowLevel = UIWindow.Level.normal + 1',GUEST)
        self.assertIn('ScarletGuestScreenPan',GUEST)

    def test_p49_separate_unsigned_release(self):
        self.assertIn('fix/scarlet-v48-r6p49-key-host-statusbar-20261113',WF)
        self.assertIn('scarlet-v48-r6p49-key-host-statusbar-unsigned-20261113',WF)
        self.assertIn('Scarlet-Crystal-V48-R6P49-KEY-HOST-STATUSBAR-UNSIGNED.ipa',WF)
        self.assertIn('scarlet-v48-r6p48-fresh-proof-crop-unsigned-20261113',WF)

if __name__=='__main__': unittest.main()
