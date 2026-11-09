"""Guard PR48 layout, full-screen launch and orientation policy."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
TAB=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
PATCH=(ROOT/'integration/apply_scarlet_host.py').read_text()

class GuestTabNoResize(unittest.TestCase):
    def test_original_pr48_fullscreen_launch_unchanged(self):
        self.assertIn('try await app.runApp()',HOST)
        self.assertNotIn('try await app.runApp(multitask: true)',HOST)
        self.assertNotIn('LCMultitaskMode',HOST)

    def test_control_is_guest_side_only_and_does_not_resize_guest(self):
        self.assertIn('ScarletFullscreenGuestTabInstaller',TAB)
        self.assertIn('UIApplicationDidBecomeActiveNotification',PATCH)
        self.assertIn('TweakLoader/UIKit+GuestHooks.m',PATCH)
        self.assertIn('NSClassFromString(@\\"ScarletFullscreenGuestTabInstaller\\")',PATCH)
        self.assertIn('SCARLET_PR48_GUEST_ROUND_TAB',TAB)
        self.assertIn('SCARLET_PR48_GUEST_EXIT',TAB)
        for prohibited in ('root.view.frame =', 'window.frame =',
                           'appSceneVC.view.frame =', 'UISupportedInterfaceOrientations',
                           'supportedInterfaceOrientations =', 'orientationLock =',
                           'UIInterfaceOrientationMaskLandscape'):
            self.assertNotIn(prohibited,TAB)
        self.assertIn('widthConstraint?.constant',TAB)
        self.assertIn('heightConstraint?.constant',TAB)

    def test_guest_exit_relanches_original_pr48_host(self):
        self.assertIn('defaults.set("ui", forKey: "selected")',TAB)
        self.assertIn('defaults.removeObject(forKey: "selectedContainer")',TAB)
        self.assertIn('LCSharedUtils.launchToGuestApp(withClassicMode: 0)',TAB)
        self.assertNotIn('removeItem(',TAB)
        self.assertNotIn('LCCertificateData',TAB)
        self.assertIn('실행 중인 앱',TAB)
        self.assertIn('현재 실행 중 · 전체화면',TAB)
if __name__=='__main__':unittest.main()
