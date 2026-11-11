"""V48-R7 source contracts: status bar exclusion geometry without touching V48 Pan/outside shield.
Source tests do NOT prove visible iPhone Dynamic Island avoidance.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
I=(R/'integration/apply_scarlet_host.py').read_text()
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
SCENE=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
UI=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
DIAG=(R/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
WF=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class StatusBarExclusionOnly(unittest.TestCase):
 def test_status_frame_not_just_insets(self):
  self.assertIn('void ScarletPilotApplyStatusBarGeometry(',I)
  self.assertIn('settings.statusBarAvoidanceFrame = exclusion;',I)
  self.assertIn('settings.statusBarHeight = MAX(0, reserved);',I)
  self.assertIn('CGRectGetMaxY(statusFrame)',I)
  self.assertIn('MAX(safe.top, CGRectGetMaxY(statusFrame))',I)
  self.assertIn('CGRectMake(0, 0, width, MAX(0, reserved))',I)
  self.assertIn('settings.respondsToSelector',I.replace('[settings respondsToSelector:', 'settings.respondsToSelector'))
  self.assertNotIn('reserved = 62',I)
 def test_both_scene_paths_shared_not_guest_scene_reshape(self):
  self.assertIn('ScarletPilotApplyStatusBarGeometry(settings,',I)
  self.assertIn('ScarletPilotApplyStatusBarGeometry(settings, homeScene, safe)',I)
  self.assertIn('if(self.scarletNativeFullscreenSlot) {',I)
  self.assertIn('if(scarletPilot) {',I)
  self.assertIn('if(LCHasRemoteSheetProviderSelector && self.ui_viewServiceComponent)',I)
  self.assertIn('"pilotStatusBarAvoidance"',I)
  self.assertIn('vc.scaleRatio = 1',SCENE)
  self.assertNotIn('CGAffineTransform',SCENE)
 def test_native_diagnostics_and_working_panel_remain(self):
  self.assertIn('pilot_statusbar_avoidance_applied',HOST)
  self.assertIn('"avoidance_height_pt"',DIAG)
  self.assertIn('"avoidance_width_pt"',DIAG)
  self.assertIn('private final class ScarletSwitcherOutsideShield: UIControl',UI)
  self.assertIn('dismissState?.requestClose()',UI)
  self.assertIn('ScarletGuestScreenPan(onChange: traceOriginalPan)',UI)
  self.assertIn('private static func panChanged(',UI)
 def test_versioned_r7_without_resurrected_v49(self):
  self.assertIn('Scarlet-Crystal-V48-R7-UNSIGNED.ipa',WF)
  self.assertIn('scarlet-v48-r7-unsigned-20261111',WF)
if __name__=='__main__':unittest.main()
