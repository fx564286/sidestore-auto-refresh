"""R5Z source contracts from the iPhone R5Y 2026-11-11 05:45 trace.
Source/unit tests do not claim that iPhone optical or touch issues resolved.
"""
from pathlib import Path
import hashlib,unittest
R=Path(__file__).resolve().parents[1]
TAB=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
GLUE=(R/'integration/apply_scarlet_host.py').read_text()
WORKFLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class WindowTouchAndGuestReadiness(unittest.TestCase):
 def test_native_window_touch_path_does_not_change_original_pan(self):
  self.assertIn('override func sendEvent(_ event: UIEvent)',TAB)
  self.assertIn('super.sendEvent(event)',TAB)
  self.assertIn('outsideTouchStart.insert(ObjectIdentifier(touch))',TAB)
  self.assertIn('outside_window_touch_began',TAB)
  self.assertIn('outside_window_touch_ended',TAB)
  self.assertIn('dismissState?.requestClose()',TAB)
  self.assertIn('guard outsideTouchStart.remove(key) != nil',TAB)
  self.assertIn('!panelRect.insetBy(dx: -3, dy: -3).contains(p)',TAB)
  self.assertIn('ScarletGuestScreenPan(onChange: traceOriginalPan)',TAB)
  self.assertIn('private static func panChanged(',TAB)
  self.assertNotIn('UILongPressGestureRecognizer(',TAB)
 def test_window_ready_poll_outlasts_6s_delayed_activation(self):
  self.assertIn('ScarletGuestRootAttempts >= 60',GLUE)
  self.assertIn('0.5 * NSEC_PER_SEC',GLUE)
  self.assertIn('ScarletGuestRootApplied = YES;',GLUE)
  self.assertIn('safearea_root_ready_after_window',GLUE)
  self.assertIn('safearea_root_window_timeout',GLUE)
  self.assertIn('safearea_root_pilot_disabled',GLUE)
  self.assertIn('ScarletGuestInstallRootSafeAreaGetter();',GLUE)
  self.assertIn('safearea_root_observer_installed',GLUE)
  self.assertNotIn('for(NSNumber *delay in @[@0.2, @0.6, @1.2, @2.5])',GLUE)
  self.assertIn('unmodified_passthrough_guest_root_inset',GLUE)
 def test_original_v48_pan_bytes_unchanged(self):
  c=TAB[TAB.index('// UIkit pan tracks finger'):TAB.index('@objc(ScarletFullscreenGuestTabInstaller)')]
  p=TAB[TAB.index('    private static func panChanged('):TAB.index('    private static func resizeOverlay(')]
  self.assertEqual(hashlib.sha256(c.encode()).hexdigest(),'105c875b0c09a1c6b567859da3ee1e273a3fb32e471f75b026bcdff4af561ff2')
  self.assertEqual(hashlib.sha256(p.encode()).hexdigest(),'37aaf834d19592d3846786abc794dac6365dc19fc9bdc96213251095555c24ce')
 def test_new_release(self):
  self.assertIn('scarlet-v48-r5z-unsigned-20261111',WORKFLOW)
  self.assertIn('Scarlet-Crystal-V48-R5Z-UNSIGNED.ipa',WORKFLOW)
if __name__=='__main__':unittest.main()
