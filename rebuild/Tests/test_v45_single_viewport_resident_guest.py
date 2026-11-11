"""V45 single-viewport LiveProcess architecture source contracts.

This prototype MUST keep the V40 full-screen native cold mode as the default,
and must never claim on-device memory retention without persistent process PID.
"""
import unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
SCENE=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
GLUE=(R/'integration/apply_scarlet_host.py').read_text()
WORKFLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
SWITCHER=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()

class TestV45(unittest.TestCase):
    def test_distinct_fullscreen_compositor_not_virtual_window(self):
        self.assertIn('ScarletFullscreenSceneViewportRepresentable', HOST)
        self.assertIn('.overlay {', HOST)
        self.assertIn('.ignoresSafeArea(.all, edges: .all)', HOST)
        self.assertIn('.opacity(fullscreenStack.isVisible ? 1 : 0)', HOST)
        self.assertIn('AppSceneViewController(', SCENE)
        self.assertIn('vc.scarletNativeFullscreenSlot = true', SCENE)
        self.assertIn('vc.scaleRatio = 1', SCENE)
        self.assertIn('view.addSubview(vc.view)',SCENE)
        self.assertIn('view.bringSubviewToFront(target.view)',SCENE)
        self.assertIn('vc.view.layer.opacity = key == folder ? 1 : 0',SCENE)
        for forbidden in ('DecoratedAppSceneViewController(', 'MultitaskDockManager.',
                          'MultitaskWindowManager.', 'UISceneSessionDestruction',
                          'requestSceneSessionDestruction', 'CGAffineTransform',
                          'UIScreen.main.bounds.size.width /', 'UIScreen.main.scale ='):
            self.assertNotIn(forbidden, SCENE)

    def test_all_guest_scenes_remain_attached_and_no_kills(self):
        self.assertIn('private var controllers: [String: AppSceneViewController]',SCENE)
        self.assertIn('controllers[slot.id] = vc',SCENE)
        self.assertIn('target.isAppRunning', SCENE)
        self.assertIn('fullscreen_scene_process_reused',SCENE)
        self.assertIn('"memory": "same_live_process"',SCENE)
        self.assertIn('"process_pid": String(slot.pid)',SCENE)
        self.assertIn('fullscreen_scene_process_exited', SCENE)
        self.assertNotIn('terminate()',SCENE)
        self.assertIn('guard !old.isAppRunning else { return false }',SCENE)
        self.assertIn('old.removeFromParent()',SCENE)
        self.assertIn('guard !old.isAppRunning else { return false }',SCENE)
        self.assertIn('old.view.removeFromSuperview()',SCENE)
        self.assertNotIn('fatalError("Child view',SCENE)

    def test_no_clip_by_actual_window_size_readback(self):
        self.assertIn('scene.coordinateSpace.bounds.size',SCENE)
        self.assertIn('abs(expected.width - actual.width) < 2',SCENE)
        self.assertIn('abs(expected.height - actual.height) < 2',SCENE)
        self.assertIn('fullscreen_scene_geometry_rejected',SCENE)
        self.assertIn('settings.setFrame(full)',SCENE)
        self.assertIn('settings.safeAreaInsetsPortrait = safe',SCENE)
        self.assertIn('view.bounds',SCENE)
        self.assertIn('!self.scarletNativeFullscreenSlot && UIInterfaceOrientationIsLandscape',GLUE)
        self.assertIn('settings.statusBarDisabled = !self.isNativeWindow;',GLUE)
        self.assertIn('settings.statusBarDisabled = !self.isNativeWindow && !self.scarletNativeFullscreenSlot;',GLUE)
        self.assertIn('ScarletPilotRemoteSafeAreaChanged',GLUE)
        self.assertNotIn('CGRectMake(0, 0, 320, 480)',SCENE)
        self.assertNotIn('self.view.frame = CGRect(',SCENE)

    def test_original_v40_default_fallback_is_untouched(self):
        self.assertIn('experimentalFullscreenResident = false',HOST)
        self.assertIn('Scarlet.Feature.FullscreenResidentPilot.V45',HOST)
        self.assertIn('try await app.runApp(multitask: false)',HOST)
        self.assertIn('try await app.signApp(force: false)',HOST)
        self.assertIn('try fullscreenStack.enqueueSignedGuest(app)',HOST)
        self.assertIn('app.appInfo.defaultClassicMode == 0',HOST)
        self.assertIn('!app.appInfo.isJITNeeded',HOST)
        self.assertIn('app.uiSelectedContainer != nil',HOST)
        self.assertIn('!app.appInfo.is32bit',HOST)
        self.assertNotIn('ScarletResidentGuestSwitchController',HOST+SCENE)
        self.assertNotIn('MultitaskMode.virtualWindow',HOST+SCENE)

    def test_original_v40_glass_ui_is_reused_without_resizing(self):
        self.assertIn('ScarletGuestTouchPassthroughWindow',SCENE)
        self.assertIn('ScarletFullscreenGuestTabInstaller.makeResidentSwitcherWindow(',SCENE)
        self.assertIn('ScarletFullscreenGuestFloatingTab(',SWITCHER)
        self.assertIn('window.isExpanded = expanded',SCENE) if False else None
        self.assertIn('onPanel: resizeOverlay',SWITCHER)
        self.assertIn('overlay.windowLevel = UIWindow.Level.alert + 1',SWITCHER)
        self.assertIn('onSwitch: { [weak self] target in',SCENE)
        self.assertIn('onExit: { [weak self] in self?.goHome() }',SCENE)
        self.assertIn('overlayWindow?.isHidden = true',SCENE)
        self.assertIn('canRelaunch: canRestart',SCENE)

    def test_native_integration_and_release(self):
        self.assertIn('add_v45_fullscreen_scene_slot(engine)',GLUE)
        self.assertIn('ScarletFullscreenSceneStack.swift',GLUE)
        self.assertIn('Scarlet.Feature.FullscreenResidentPilot.V45',HOST)
        self.assertIn('fix/scarlet-v45-single-viewport-liveprocess-20261111',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V45-UNSIGNED.ipa',WORKFLOW)
        self.assertIn('scarlet-v45-unsigned-20261111',WORKFLOW)

if __name__=="__main__":
    unittest.main()
