"""PR48 AirPods-style glass, app switch, and no-resize invariants."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
GUEST=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
PATCH=(ROOT/'integration/apply_scarlet_host.py').read_text()

class GuestAirPodsGlassSwitcher(unittest.TestCase):
    def test_native_ios26_material_and_airpods_style_spring(self):
        for s in ('UIGlassEffect(style: .regular)', 'UIVisualEffectView(effect: glass)',
                  'GlassEffectContainer(spacing: 14)',
                  'ScarletUIKitGlassBackdrop(radius: radius)',
                  'switch_panel_content_rendered',
                  'spring(response: 0.47, dampingFraction: 0.82)',
                  'UIView.performWithoutAnimation',
                  'UIImpactFeedbackGenerator(style: .soft)',
                  'SCARLET_PR48_AIRPODS_GLASS_PANEL'):
            self.assertIn(s,GUEST)

    def test_scan_real_installed_guests_and_switch_via_original_lc_bootstrap(self):
        for s in ('LC_HOME_PATH', 'LCSharedUtils.appGroupPath()',
                  'LCAppInfo.plist', 'LCContainers', 'LCDataUUID',
                  'lastLaunched', 'selectedContainer',
                  'getenv("LC_HOME_PATH")',
                  'UserDefaults.lc()', 'switch_candidates_scanned',
                  'switch_relaunch_requested', 'switchGuest(to target:',
                  'LCSharedUtils.launchToGuestApp(withClassicMode: target.classicMode)',
                  'SCARLET_PR48_GUEST_SWITCH_TARGET', '전환 가능한 앱 없음'):
            self.assertIn(s,GUEST)
        self.assertIn('for url in items where url.pathExtension.lowercased() == "app"', GUEST)
        self.assertIn('guard !found.contains(folder)',GUEST)
        self.assertIn('!needsJIT && !nonInjected',GUEST)
        self.assertIn('target.canSwitch',GUEST)

    def test_pr48_layout_and_guest_security_unchanged(self):
        self.assertIn('try await app.runApp()',HOST)
        self.assertNotIn('try await app.runApp(multitask: true)',HOST)
        self.assertIn('ScarletGuestTouchPassthroughWindow(windowScene: scene)',GUEST)
        self.assertIn('floating.frame = next',GUEST)
        self.assertIn('Stay non-key to protect guest keyboard',GUEST)
        for s in ('original.frame =', 'appSceneVC.view.frame =',
                  'UISupportedInterfaceOrientations',
                  'orientationLock =', 'LCCertificateData',
                  'removeItem(at:', 'runApp(multitask: true)'):
            self.assertNotIn(s,GUEST)
        self.assertIn('dlopen(frameworkPath.UTF8String, RTLD_LAZY | RTLD_GLOBAL)',PATCH)

if __name__ == '__main__': unittest.main()
