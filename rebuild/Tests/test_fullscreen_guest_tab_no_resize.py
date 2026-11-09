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
        self.assertIn('ScarletGuestTouchPassthroughWindow(windowScene: scene)',TAB)
        self.assertIn('floatingWindow.frame = next',TAB)
        self.assertIn('overlay.isHidden = false',TAB)
        self.assertIn('overlay.windowLevel = UIWindow.Level.alert + 1',TAB)
        self.assertIn('fullscreen_tab_mounted',TAB)
        self.assertIn('floatingWindow?.isHidden = true',TAB)
        self.assertNotIn('original.frame =', TAB)

    def test_essential_framework_loaded_in_guest_and_lifecycle_retry(self):
        self.assertIn('LiveContainerSwiftUI.framework/LiveContainerSwiftUI',PATCH)
        self.assertIn('dlopen(frameworkPath.UTF8String, RTLD_LAZY | RTLD_GLOBAL)',PATCH)
        self.assertIn('NSUserDefaults.lcMainBundle.bundlePath',PATCH)
        self.assertIn('UIWindowDidBecomeKeyNotification',PATCH)
        self.assertIn('UISceneDidActivateNotification',PATCH)
        self.assertIn('framework_loaded',PATCH)
        self.assertIn('installer_class_unavailable',PATCH)
        self.assertIn('dispatch_after(',PATCH)
        self.assertNotIn('runApp(multitask: true)',HOST)

    def test_guest_exit_relanches_original_pr48_host(self):
        self.assertIn('defaults.set("ui", forKey: "selected")',TAB)
        self.assertIn('defaults.removeObject(forKey: "selectedContainer")',TAB)
        self.assertIn('LCSharedUtils.launchToGuestApp(withClassicMode: 0)',TAB)
        self.assertNotIn('removeItem(',TAB)
        self.assertNotIn('LCCertificateData',TAB)
        self.assertIn('앱 전환',TAB)
        self.assertIn('accessibilityLabel("현재 실행 중")',TAB)
if __name__=='__main__':unittest.main()
