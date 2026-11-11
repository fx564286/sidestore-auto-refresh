"""V48-R5: a visible native outside-dismiss shield and post-attach safe-area sync.
Source test; not a claim of real iPhone gesture or optical verification.
"""
from pathlib import Path
import hashlib,unittest
R=Path(__file__).resolve().parents[1]
TAB=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
STACK=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
GLUE=(R/'integration/apply_scarlet_host.py').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class NativeTwoIssueRegression(unittest.TestCase):
 def test_outside_tap_is_real_ui_control_direct_close(self):
  self.assertIn('private final class ScarletSwitcherOutsideShield: UIControl',TAB)
  self.assertIn('override func point(inside point: CGPoint, with event: UIEvent?) -> Bool',TAB)
  self.assertIn('return !owner.panelRect.insetBy(dx: -3, dy: -3).contains(point)',TAB)
  self.assertIn('addSubview(shield)',TAB)
  self.assertIn('bringSubviewToFront(shield)',TAB)
  self.assertIn('for: .touchUpInside',TAB)
  self.assertIn('dismissState?.requestClose()',TAB)
  self.assertIn('closeGeneration &+= 1',TAB)
  self.assertIn('onChange(of: dismissState.closeGeneration)',TAB)
  self.assertIn('closePanel() // Original V48 closePanel and button remain.',TAB)
  self.assertNotIn('override func hitTest(',TAB)
  self.assertNotIn('switch_outside_native_dismiss_dispatched',TAB)
  self.assertNotIn('NotificationCenter.default.post(name: Self.outsideDismiss',TAB)
  self.assertEqual(TAB.count('overlay.enableNativeOutsideDismiss()'),2)
  self.assertEqual(TAB.count('overlay.dismissState = dismissState'),2)
 def test_attached_guest_remote_safe_insets_and_no_resizing(self):
  self.assertIn('private func synchronizeAttachedGuestSafeAreas(_ scene: UIWindowScene)',STACK)
  self.assertIn('scene.statusBarManager?.statusBarFrame.maxY ?? 0',STACK)
  self.assertNotIn('controller.additionalSafeAreaInsets = .zero',STACK)
  self.assertNotIn('controller.additionalSafeAreaInsets = UIEdgeInsets(',STACK)
  self.assertIn('observedRemoteInsets[key] = safe',STACK)
  self.assertIn('SCGeometryResolve(self, safe, settings.interfaceOrientation',GLUE)
  self.assertIn('settings.safeAreaEdgeInsets = safe;',GLUE)
  self.assertIn('synchronizeAttachedGuestSafeAreas(scene)',STACK)
  self.assertIn('guest_geometry_authority_observed',STACK)
  self.assertIn('attached_guest_safearea_unavailable',STACK)
  self.assertIn('vc.scaleRatio = 1',STACK)
  self.assertIn('settings.setFrame(full)',STACK)
  self.assertNotIn('CGAffineTransform',STACK)
  self.assertIn('ScarletPilotHostInsets',GLUE)
 def test_preserves_original_v48_pan_source_sha(self):
  c=TAB[TAB.index('// UIkit pan tracks finger'):TAB.index('@objc(ScarletFullscreenGuestTabInstaller)')]
  p=TAB[TAB.index('    private static func panChanged('):TAB.index('    private static func resizeOverlay(')]
  self.assertEqual(hashlib.sha256(c.encode()).hexdigest(),'105c875b0c09a1c6b567859da3ee1e273a3fb32e471f75b026bcdff4af561ff2')
  self.assertEqual(hashlib.sha256(p.encode()).hexdigest(),'37aaf834d19592d3846786abc794dac6365dc19fc9bdc96213251095555c24ce')
 def test_release_version(self):
  self.assertIn('scarlet-v48-r5-unsigned-20261111',W)
  self.assertIn('Scarlet-Crystal-V48-R5-UNSIGNED.ipa',W)
if __name__ == '__main__':unittest.main()
