"""V48-R4: native outside tap and iOS27 remote FBScene safe-area contracts.
Unit/source verification only; final visual hit behavior requires iPhone QA.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
TAB=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
GLUE=(R/'integration/apply_scarlet_host.py').read_text()
SCENE=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
WORKFLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class NativeOutsideAndIsland(unittest.TestCase):
 def test_native_window_tap_outside_closes_same_panel(self):
  self.assertIn('private final class ScarletSwitcherOutsideShield: UIControl',TAB)
  self.assertIn('final class ScarletGuestTouchPassthroughWindow: UIWindow {',TAB)
  self.assertIn('return !owner.panelRect.insetBy(dx: -3, dy: -3).contains(point)',TAB)
  self.assertIn('shield.isHidden = !isExpanded',TAB)
  self.assertIn('bringSubviewToFront(shield)',TAB)
  self.assertIn('for: .touchUpInside',TAB)
  self.assertIn('dismissState?.requestClose()',TAB)
  self.assertIn('.onChange(of: dismissState.closeGeneration)',TAB)
  self.assertIn('closePanel() // Original V48 closePanel and button remain.',TAB)
  self.assertEqual(TAB.count('overlay.enableNativeOutsideDismiss()'),2)
  self.assertNotIn('override func hitTest(',TAB)
  self.assertIn('hypot(point.x - buttonCenter.x,',TAB)
 def test_original_v48_pan_implementation_not_replaced(self):
  self.assertEqual(TAB.count('let pan = UIPanGestureRecognizer(target: panHandler,'),2)
  self.assertIn('ScarletGuestScreenPan(onChange: traceOriginalPan)',TAB)
  self.assertIn('private static func panChanged(screenPoint: CGPoint',TAB)
  self.assertNotIn('UILongPressGestureRecognizer(',TAB)
  self.assertIn('floating_tab_position_saved',TAB)
 def test_remote_scene_initial_and_live_update_target_only_pilot(self):
  self.assertIn('ScarletPilotHostInsets(',GLUE)
  self.assertIn('settings.statusBarDisabled = !self.isNativeWindow && !self.scarletNativeFullscreenSlot;',GLUE)
  self.assertIn('objc_setAssociatedObject(scene,',GLUE)
  self.assertIn('objc_getAssociatedObject(self,',GLUE)
  self.assertIn('sel_registerName("scarletNativeFullscreenSlot")',GLUE)
  self.assertIn('BOOL scarletPilot =',GLUE)
  self.assertIn('if(scarletPilot) {',GLUE)
  self.assertIn('settings.safeAreaEdgeInsets = safe;',GLUE)
  self.assertIn('settings.safeAreaInsetsPortrait =',GLUE)
  self.assertIn('settings.peripheryInsets = safe;',GLUE)
  self.assertIn('CGRectGetMaxY(hostScene.statusBarManager.statusBarFrame)',GLUE)
  self.assertNotIn('CGRectGetMaxY(homeScene.statusBarManager.statusBarFrame)',GLUE)
  self.assertIn('pilotFBSceneUpdates',GLUE)
  self.assertIn('[self hook__performUpdateWithoutActivation:updateBlock];',GLUE)
  self.assertIn('window.windowLevel == UIWindowLevelNormal && !window.isHidden',GLUE)
  self.assertIn('if(LCHasRemoteSheetProviderSelector && self.ui_viewServiceComponent)',GLUE)
  self.assertIn('pilotRemoteSafeArea',GLUE)
  self.assertIn('"ScarletPilotRemoteSafeAreaChanged"',HOST)
  self.assertIn('"pilot_remote_safearea_applied"',HOST)
  self.assertIn('"zero_remote_scene_safearea"',HOST)
 def test_original_guest_presentation_not_resized(self):
  self.assertNotIn('CGAffineTransform',SCENE)
  self.assertIn('vc.scaleRatio = 1',SCENE)
  self.assertIn('settings.setFrame(full)',SCENE)
  self.assertIn('outside_shield_close_handled',TAB)
  self.assertIn('if false && !installChoices.isEmpty {',TAB)
 def test_release(self):
  self.assertIn('scarlet-v48-r4-unsigned-20261111',WORKFLOW)
  self.assertIn('Scarlet-Crystal-V48-R4-UNSIGNED.ipa',WORKFLOW)
if __name__ == '__main__':unittest.main()
