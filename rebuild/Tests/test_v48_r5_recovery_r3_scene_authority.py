"""R3 assertions after actual R2 iOS 27.2 log: 62pt->0pt 21+ repeated.
This tests architecture and offline state scenarios, not on-device rendering.
"""
from pathlib import Path
import hashlib,unittest
ROOT=Path(__file__).resolve().parents[1]
G=(ROOT/'integration/apply_scarlet_host.py').read_text()
S=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
T=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
W=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class R3SceneAuthority(unittest.TestCase):
 def test_scene_scoped_resolver_and_never_cache_zero(self):
  for token in ('ScarletSceneGeometryAuthority.h',
                'SCGeometryCacheKey',
                'objc_getAssociatedObject(remoteScene, SCGeometryCacheKey())',
                'objc_setAssociatedObject(remoteScene, SCGeometryCacheKey()',
                'if(!UIInterfaceOrientationIsPortrait(orientation)) return measured;',
                'BOOL valid = isfinite(measured.top) && measured.top >= 18',
                'measured.top = previous.top;',
                'if(didRecover) *didRecover = YES;',
                'cached_scene_geometry',
                'SCGeometryShouldReport(self, safe, recovered)'):
   self.assertIn(token,G)
 def test_single_fbscene_writer_not_repeated_swift_insets(self):
  for forbidden in ('controller.additionalSafeAreaInsets = .zero',
                    'controller.additionalSafeAreaInsets = UIEdgeInsets(',
                    'settings.safeAreaEdgeInsets = safe',
                    'controller.updateSettings { settings in'):
   self.assertNotIn(forbidden,S)
  self.assertIn('guest_geometry_authority_observed',S)
  self.assertIn('native_hosting_safearea_owner_readback',S)
  self.assertIn('scarletApplyHostingContentSafeArea:',G)
  self.assertNotIn('owner.additionalSafeAreaInsets = next;',G)
  self.assertNotIn('hook_scarletGuestSendEvent',G)
  self.assertNotIn('ScarletGuestRootSafeAreaOverride',G)
  self.assertIn('settings.setFrame(full)',S)
  self.assertIn('vc.scaleRatio = 1',S)
 def test_keep_successful_r2_outside_tap(self):
  for text in ('resident_host_background_tap_received',
               'outsideDismissGesture',
               'overlay.dismissState?.requestClose()'):
   self.assertIn(text,S)
  x=T[T.index('// UIkit pan tracks finger'):T.index('@objc(ScarletFullscreenGuestTabInstaller)')]
  p=T[T.index('    private static func panChanged('):T.index('    private static func resizeOverlay(')]
  self.assertEqual(hashlib.sha256(x.encode()).hexdigest(),'105c875b0c09a1c6b567859da3ee1e273a3fb32e471f75b026bcdff4af561ff2')
  self.assertEqual(hashlib.sha256(p.encode()).hexdigest(),'37aaf834d19592d3846786abc794dac6365dc19fc9bdc96213251095555c24ce')
 def test_release_branch(self):
  self.assertIn('scarlet-v48-r5-recovery-r3-unsigned-20261111',W)
  self.assertIn('Scarlet-Crystal-V48-R5-RECOVERY-R3-UNSIGNED.ipa',W)
if __name__=='__main__':unittest.main()
