"""Signed P40 PID2454 reproduction guard: avoid global shift and +62 reentry."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
GEN=(R/'integration/apply_scarlet_host.py').read_text()
GUEST=(R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
REC=(R/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
WF=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class P41Adaptive(unittest.TestCase):
 def test_only_bounded_pid_specific_unsafe_controls_activate_slot(self):
  for key in ('onTopRiskMeasured','onUnsafeGuestControls(pid:',
      'unsafe >= 3','first >= -3 && first < top - 15',
      '!chromeEligiblePIDs.contains(pid)','sample == 650 || sample == 2600',
      'chromeEligiblePIDs.insert(pid)','guest_chrome_adaptive_qualified',
      'guest_chrome_adaptive_slot_applied','chromeEligiblePIDs.contains(vc.pid)',
      'vc.scarletApplyNativeTransparentChromeSlot(reserved)',
      'vc.view.frame = rect','settings.setFrame(rect)'):
   self.assertIn(key,HOST,key)
  self.assertNotIn('vc.scarletNativeTransparentChromeSlot = chromeTop(in: scene) > 0',HOST)
 def test_safe_guests_preserve_native_full_window_and_no_auto_resize_growth(self):
  for key in ('vc.scarletNativeTransparentChromeSlot = false',
      'vc.view.frame = contentSlot(in: scene, reserved: false)',
      'vc.view.autoresizingMask = []', 'contentSlot(in scene: UIWindowScene, reserved: Bool)',
      'native_fullscreen_preserved','selected_risky_guest_only',
      'scale_milli', 'transparentChrome.isUserInteractionEnabled = false',
      'scene.interfaceOrientation.isPortrait'):
   self.assertIn(key,HOST,key)
  self.assertNotIn('vc.view.autoresizingMask =\n                [.flexibleWidth, .flexibleHeight]',HOST)
 def test_native_fbscene_mode_is_updated_before_native_geometry_update(self):
  self.assertIn('scarletApplyNativeTransparentChromeSlot:(BOOL)enabled',GEN)
  self.assertIn('self.scarletNativeTransparentChromeSlot = enabled',GEN)
  self.assertIn('objc_setAssociatedObject(remote,',GEN)
  self.assertIn('if(chrome && UIInterfaceOrientationIsPortrait(settings.interfaceOrientation))',GEN)
 def test_confirmed_guest_pid_windows_cannot_reapply_62_on_reentry(self):
  for key in ('TransparentChromeActivePIDs.V1','[activePIDs containsObject:@(getpid())]',
      'scarletIslandConfirmedChromeWindowKey',
      'BOOL confirmedEarlier', 'frameConfirmed || confirmedEarlier',
      'root.additionalSafeAreaInsets=extra','own.doubleValue',
      'guest_transparent_chrome_slot_preserved','guest_transparent_chrome_slot_unpadded'):
   self.assertIn(key,GUEST,key)
  self.assertIn('Scarlet.Guest.TransparentChromeActivePIDs.V1',HOST)
 def test_previous_guest_header_mutator_disabled_and_diagnostics_complete(self):
  p38=GUEST.split('// R6P38_LAYOUT_OWNER_BEGIN',1)[1].split('// R6P38_LAYOUT_OWNER_END',1)[0]
  self.assertNotIn('    ScarletIslandTryMeasuredHeaderConstraintBridge(',p38)
  for field in ('"slot_top_pt"', '"slot_y_pt"','"slot_height_pt"',
                '"remote_content_height_pt"','"scale_milli"'):
   self.assertIn(field,REC,field)
  self.assertIn('guest_content_geometry_probe',HOST)
  self.assertIn('ScarletIslandScheduleContentProbe(window, root, target)',GUEST)
 def test_release_distinct_and_original_untouched(self):
  self.assertIn('scarlet-v48-r6p41-adaptive-chrome-unsigned-20261113',WF)
  self.assertIn('Scarlet-Crystal-V48-R6P41-ADAPTIVE-CHROME-UNSIGNED.ipa',WF)
if __name__=='__main__':unittest.main()
