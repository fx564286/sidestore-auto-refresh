"""R5 recovery R2 invariants: original guest runtime and native host-only fixes.
Source checks + pinned integration smoke are NOT iPhone optical verification.
"""
from pathlib import Path
import hashlib,unittest
R=Path(__file__).resolve().parents[1]
T=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
S=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
I=(R/'integration/apply_scarlet_host.py').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class RecoveryR2(unittest.TestCase):
 def test_restored_r5_gesture_keeps_classic_and_r2_new_resident_owner(self):
  self.assertIn('residentHostOwnsOutsideTaps = true',T)
  self.assertIn('if residentHostOwnsOutsideTaps {',T)
  self.assertIn('return panelRect.insetBy(dx: -3, dy: -3).contains(point)',T)
  self.assertIn('return super.point(inside: point, with: event)',T)
  self.assertIn('expandedChanged?(isExpanded)',T)
  self.assertIn('resident_host_background_gesture_installed',S)
  self.assertIn('resident_host_background_tap_received',S)
  self.assertIn('UITapGestureRecognizer(target: self',S)
  self.assertIn('view.addGestureRecognizer(outside)',S)
  self.assertIn('setResidentOutsideDismissEnabled(expanded)',S)
  self.assertIn('overlay.dismissState?.requestClose()',S)
  self.assertIn('outside.cancelsTouchesInView = true',S)
  self.assertIn('tap.isEnabled = enabled',S)
  self.assertIn('if let scene = view.window?.windowScene {',S)
 def test_pure_objc_nested_host_owner_not_guest_global_swizzle(self):
  self.assertIn('scarletApplyHostingContentSafeArea:',I)
  self.assertIn('self.hostingController.sceneViewController',I)
  self.assertIn('owner.additionalSafeAreaInsets = next;',I)
  self.assertIn('CGFloat nativeTop = MAX(0, observed.top - previous.top);',I)
  self.assertIn('CGFloat nativeBottom = MAX(0, observed.bottom - previous.bottom);',I)
  self.assertIn('controller.scarletApplyHostingContentSafeArea(safe)',S)
  self.assertIn('lastHostingOwnerProbes[key] != ownerSignature',S)
  self.assertIn('native_hosting_safearea_owner_readback',S)
  self.assertIn('synchronizeAttachedGuestSafeAreas(scene)',S)
  self.assertIn('settings.setFrame(full)',S)
  self.assertIn('vc.scaleRatio = 1',S)
  for forbidden in ('hook_scarletGuestSendEvent', 'ScarletGuestRootSafeAreaOverride',
                    'ScarletGuestInstallRootSafeAreaGetter'):
   self.assertNotIn(forbidden,I)
   self.assertNotIn(forbidden,T)
 def test_verbatim_v48_pan_unmodified(self):
  c=T[T.index('// UIkit pan tracks finger'):T.index('@objc(ScarletFullscreenGuestTabInstaller)')]
  p=T[T.index('    private static func panChanged('):T.index('    private static func resizeOverlay(')]
  self.assertEqual(hashlib.sha256(c.encode()).hexdigest(),'105c875b0c09a1c6b567859da3ee1e273a3fb32e471f75b026bcdff4af561ff2')
  self.assertEqual(hashlib.sha256(p.encode()).hexdigest(),'37aaf834d19592d3846786abc794dac6365dc19fc9bdc96213251095555c24ce')
 def test_original_r5_and_recovery_release_coexist(self):
  self.assertIn('scarlet-v48-r5-recovery-r2-unsigned-20261111',W)
  self.assertIn('Scarlet-Crystal-V48-R5-RECOVERY-R2-UNSIGNED.ipa',W)
  self.assertIn('Scarlet-Crystal-V48-R5-RECOVERY-UNSIGNED.ipa',W)
if __name__=='__main__':unittest.main()
