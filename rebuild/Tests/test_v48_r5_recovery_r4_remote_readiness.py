"""R4 regression: guest process PID precedes remote UIKit content attach.
These tests are source checks; no screenshot or iPhone black-screen fix is claimed.
"""
from pathlib import Path
import hashlib,unittest
R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
BRIDGE=(R/'integration/apply_scarlet_host.py').read_text()
SW=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
FLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class R4NativeSceneReady(unittest.TestCase):
 def test_delegated_native_attachment_after_content_subview(self):
  for fragment in ('appSceneVCDidAttachRemoteContent:(AppSceneViewController *)vc;',
                   'self.view addSubview:_contentView',
                   'respondsToSelector:@selector(appSceneVCDidAttachRemoteContent:)',
                   '[weakSelf.delegate appSceneVCDidAttachRemoteContent:weakSelf]',
                   '- (BOOL)scarletRemoteContentReady',
                   'self.contentView.superview != self.view',
                   'self.view.window',
                   'self.presenter.scene',
                   'self.hostingController.sceneViewController.view == self.contentView'):
   self.assertIn(fragment,BRIDGE)
 def test_initial_foreground_single_write_after_real_attach(self):
  self.assertIn('- (BOOL)scarletEnsureRemoteForeground',BRIDGE)
  self.assertIn('if(![self scarletRemoteContentReady]) return NO;',BRIDGE)
  self.assertIn('static char kFirstForeground;',BRIDGE)
  self.assertIn('objc_setAssociatedObject(self,&kFirstForeground,@YES',BRIDGE)
  self.assertIn('settings.foreground = YES;',BRIDGE)
  self.assertIn('settings.deactivationReasons = 0;',BRIDGE)
  self.assertIn('fullscreen_scene_remote_foreground_confirmed',HOST)
  self.assertIn('target.scarletEnsureRemoteForeground()',HOST)
  self.assertNotIn('hook_scarletGuestSendEvent',BRIDGE)
  self.assertNotIn('ScarletGuestRootSafeAreaOverride',BRIDGE)
 def test_no_pid_only_early_opacity_display_and_bounded_retry(self):
  self.assertIn('target.scarletRemoteContentReady() else { return false }',HOST)
  self.assertIn('viewport?.isRemoteReady(folder: folder)',HOST)
  self.assertIn('attemptsRemaining: Int = 60',HOST)
  self.assertIn('250_000_000',HOST)
  self.assertIn('fullscreen_scene_waiting_for_remote_content',HOST)
  self.assertIn('fullscreen_scene_first_surface_timeout',HOST)
  self.assertIn('fullscreen_scene_remote_content_attached',HOST)
  self.assertIn('fullscreen_scene_presenter_attached',HOST)
  self.assertIn('content_ready_visibility_not_verified',HOST)
  self.assertIn('firstRevealCompleted.insert(folder).inserted',HOST)
  self.assertIn('pendingReveal.insert(folder).inserted',HOST)
  self.assertIn('if let scene = view.window?.windowScene',HOST)
  self.assertNotIn('target.contentView?.superview != nil else { return false }',HOST)
 def test_guest_pixel_geometry_and_r2_outside_close_preserved(self):
  self.assertIn('vc.scaleRatio = 1',HOST)
  self.assertIn('settings.setFrame(full)',HOST)
  self.assertIn('resident_host_background_tap_received',HOST)
  self.assertIn('overlay.dismissState?.requestClose()',HOST)
  pan=SW[SW.index('// UIkit pan tracks finger'):SW.index('@objc(ScarletFullscreenGuestTabInstaller)')]
  move=SW[SW.index('    private static func panChanged('):SW.index('    private static func resizeOverlay(')]
  self.assertEqual(hashlib.sha256(pan.encode()).hexdigest(),'105c875b0c09a1c6b567859da3ee1e273a3fb32e471f75b026bcdff4af561ff2')
  self.assertEqual(hashlib.sha256(move.encode()).hexdigest(),'37aaf834d19592d3846786abc794dac6365dc19fc9bdc96213251095555c24ce')
 def test_r3_geometry_and_r4_release_separate(self):
  self.assertIn('ScarletSceneGeometryAuthority.h',BRIDGE)
  self.assertIn('scarlet-v48-r5-recovery-r3-unsigned-20261111',FLOW)
  self.assertIn('scarlet-v48-r5-recovery-r4-unsigned-20261111',FLOW)
  self.assertIn('Scarlet-Crystal-V48-R5-RECOVERY-R4-UNSIGNED.ipa',FLOW)
if __name__=='__main__': unittest.main()
