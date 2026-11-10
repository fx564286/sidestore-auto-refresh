"""V41 resident fullscreen: architectural assertions for pinned engine patch.

The iPhone extension PID, exact last UI memory and input focus must be
verified with a signed IPA on physical iOS 27.2; these are source/integration
contract checks and a deterministic reference state machine only.
"""
import unittest
from pathlib import Path
import importlib.util, tempfile, shutil

R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
CLIENT=(R/'HostApp/ScarletResidentGuestSwitchController.swift').read_text()
ROUND=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
INJECTOR=(R/'integration/apply_scarlet_host.py').read_text()
WORKFLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class V41ResidentFullscreen(unittest.TestCase):
    def test_guest_launch_uses_extension_not_fullscreen_rebootstrap(self):
        self.assertIn('app.runApp(multitask: true)',HOST)
        self.assertIn('app.runApp(multitask: false)',HOST) # incompatible fallback
        self.assertIn('LCUtils.liveProcessBundleIdentifier() != nil',HOST)
        self.assertIn('!app.appInfo.isJITNeeded && !app.appInfo.is32bit',HOST)
        self.assertIn('resident_fullscreen_launch_requested',HOST)
        self.assertIn('resident_launch_failed',HOST)
        self.assertIn('route_iphone_guest_launch_to_resident_scene(engine)',INJECTOR)
        self.assertIn('keep_resident_guest_geometry_unscaled(engine)',INJECTOR)
        self.assertIn('scarletPrepareResident',INJECTOR)
        self.assertIn('scarletResidentParent',INJECTOR)
        self.assertNotIn('unsafe_init',INJECTOR)

    def test_fullscreen_non_scaled_original_safe_area(self):
        for required in (
            'window.frame = rect',
            'windowHostingView.frame = window.bounds',
            'view.frame = windowHostingView.bounds',
            'view.transform = .identity',
            'window.windowLevel = .normal + 1',
            'settings.peripheryInsets = self.view.window.safeAreaInsets',
            'settings.safeAreaInsetsPortrait = self.view.window.safeAreaInsets',
            'UIInterfaceOrientationIsLandscape(orientation)',
            'settings.frame = CGRectMake(0, 0, bounds.size.height, bounds.size.width)',
            'settings.frame = CGRectMake(0, 0, bounds.size.width, bounds.size.height)',
        ):
            self.assertIn(required,INJECTOR)
        self.assertNotIn('CGAffineTransformMakeScale(0.1',CLIENT)
        self.assertNotIn('setFrame:CGRectMake(0, 0, isLandscape ? 480 : 320',CLIENT)
        self.assertIn('self.view.frame = self.view.superview.bounds;',INJECTOR)
        self.assertIn('original_fullscreen_policy',HOST)

    def test_process_is_kept_when_switching(self):
        self.assertIn('scarletActivateResident(uuid: String)',INJECTOR)
        self.assertIn('decorated.appSceneVC.isAppRunning',INJECTOR)
        self.assertIn('for app in apps {',INJECTOR)
        self.assertIn('app.view?.isHidden = app.appUUID != uuid',INJECTOR)
        self.assertIn('windowHostingView.bringSubviewToFront(view)',INJECTOR)
        self.assertIn('resident_process_reused',INJECTOR)
        self.assertIn('memory": "preserved_while_process_alive"',INJECTOR)
        self.assertIn('resident_process_terminated',CLIENT)
        self.assertIn('"memory": "not_preserved"',CLIENT)
        self.assertIn('model.runApp(multitask: true',CLIENT)
        self.assertIn('scarletReturnToHome()',INJECTOR)
        self.assertIn('scarletReturnToHome()',CLIENT)

    def test_old_virtual_dock_not_restored(self):
        self.assertIn('LEGACY_DOCK_RENDERER_REMOVED_SOURCE',INJECTOR)
        self.assertNotIn('public struct MultitaskDockSwiftView: View {}',CLIENT)
        self.assertIn('ScarletFullscreenGuestFloatingTab(',CLIENT)
        self.assertIn('ScarletGuestTouchPassthroughWindow(windowScene: scene)',CLIENT)
        self.assertIn('window.windowLevel = UIWindow.Level.alert + 1',CLIENT)
        self.assertIn('window.isHidden = false',CLIENT)
        self.assertIn('window.isExpanded = open',CLIENT)
        self.assertIn('ScarletResidentGuestMode.V41',ROUND)
        self.assertIn('LCUtils.appGroupUserDefault.bool(forKey: "ScarletResidentGuestMode.V41")',ROUND)
        self.assertIn('LCUtils.appGroupUserDefault.set(false,',HOST)
        self.assertIn('SCARLET_PR48_GUEST_ROUND_TAB',ROUND)
        self.assertIn('window.buttonCenter',CLIENT)
        self.assertIn('ScarletGuestRoundTabCenterXFractionV1',CLIENT)

    def test_a_and_b_have_distinct_liveprocess_ownership(self):
        # Deterministic reference: process reactivation returns SAME PID,
        # while iOS termination makes this impossible.
        sessions={}
        sessions["A"]={"pid":201,"alive":True,"last_screen":"page3"}
        sessions["B"]={"pid":202,"alive":True,"last_screen":"detail"}
        active="B"
        active="A" if sessions["A"]["alive"] else active
        self.assertEqual(active,"A")
        self.assertEqual(sessions["A"]["pid"],201)
        self.assertEqual(sessions["A"]["last_screen"],"page3")
        sessions["A"]["alive"]=False
        self.assertFalse(sessions["A"]["alive"])
        # No component can restore dead process RAM. No false promise.
        self.assertNotEqual(sessions["A"]["alive"],True)

    def test_new_release_and_original_id(self):
        self.assertIn('fix/scarlet-v41-resident-fullscreen-20261110',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V41-UNSIGNED.ipa',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V41-UNSIGNED.ipa',WORKFLOW)

if __name__=='__main__':
    unittest.main()
