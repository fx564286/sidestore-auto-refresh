"""R5Y source regressions: distinguish direct native touch from R4 UIWindow no-op.
Does not claim iPhone runtime visual/gesture success.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
TAB=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
GLUE=(R/'integration/apply_scarlet_host.py').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class NativeHitOwnership(unittest.TestCase):
 def test_direct_hit_target_is_control_not_empty_window(self):
  self.assertIn('override func hitTest(_ point: CGPoint, with event: UIEvent?) -> UIView?',TAB)
  self.assertIn('let inShield = convert(point, to: shield)',TAB)
  self.assertIn('if shield.point(inside: inShield, with: event)',TAB)
  self.assertIn('return shield',TAB)
  self.assertNotIn('return self\n    }\n\n    override func point',TAB)
  self.assertIn('for: .touchUpInside',TAB)
  self.assertIn('dismissState?.requestClose()',TAB)
  self.assertIn('onChange(of: dismissState.closeGeneration)',TAB)
 def test_safe_area_guest_root_only(self):
  self.assertIn('ScarletGuestRootSafeAreaOverride(id view, SEL sel)',GLUE)
  self.assertIn('original.top = MAX(original.top, desired);',GLUE)
  self.assertIn('window.rootViewController.view != rootView',GLUE)
  self.assertIn('method_setImplementation(method, (IMP)ScarletGuestRootSafeAreaOverride)',GLUE)
  self.assertIn('ScarletGuestInstallRootSafeAreaGetter();',GLUE)
  self.assertIn('unmodified_passthrough_guest_root_inset',GLUE)
 def test_original_pan_and_app_size(self):
  self.assertIn('ScarletGuestScreenPan(onChange: traceOriginalPan)',TAB)
  self.assertIn('private static func panChanged(',TAB)
 def test_release(self):
  self.assertIn('scarlet-v48-r5y-unsigned-20261111',W)
  self.assertIn('Scarlet-Crystal-V48-R5Y-UNSIGNED.ipa',W)
if __name__=='__main__': unittest.main()
