"""R5 contract: failures and black first scene are separate; no guest global hooks.
Source tests do not prove KakaoTalk compatibility or Instagram render on iPhone.
"""
from pathlib import Path
import hashlib,unittest
ROOT=Path(__file__).resolve().parents[1]
SCENE=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
LOG=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
BRIDGE=(ROOT/'integration/apply_scarlet_host.py').read_text()
PAN=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
FLOW=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class R5Compatibility(unittest.TestCase):
 def test_error_domains_and_exit_measurements_are_not_filtered(self):
  for needle in ('"error_domain"', '"error_code"', '"fast_exit"', '"mode"'):
   self.assertIn(needle,LOG)
  for needle in ('"error_domain": ns?.domain',
                 '"error_code": ns.map',
                 '"stage": "before_or_during_remote_extension_request"',
                 '"fast_exit": fastExit ? "true" : "false"'):
   self.assertIn(needle,SCENE)
 def test_one_shot_classic_compatibility_only_if_no_live_guest(self):
  for needle in ('classicFallbackAttempted: Set<String>',
                 'pendingClassicFallback: Set<String>',
                 '!self.hasLiveResidentProcess, !self.pendingInPlaceLaunch',
                 'model.uiSelectedContainer?.folderName == dataUUID',
                 'let defaults = UserDefaults.lc()',
                 'defaults.set(folder, forKey: "selected")',
                 'defaults.set(dataUUID, forKey: "selectedContainer")',
                 'LCSharedUtils.launchToGuestApp(withClassicMode: 0)',
                 'original_model_container_or_defaults_unavailable',
                 'another_live_guest_or_launch_in_progress',
                 '650_000_000',
                 'self.classicFallbackAttempted.insert(folder)',
                 'experimental_guest_compatibility_route_submitted'):
   self.assertIn(needle,SCENE)
  self.assertNotIn('LCSharedUtils.revoke',SCENE)
  self.assertNotIn('removeApp(',SCENE)
 def test_existing_live_guest_is_not_relaunched_on_foreground(self):
  for needle in ('restoreForegroundOnHostActive()',
                 'fullscreen_scene_host_active_refresh',
                 'owner.setBackgroundNotificationEnabled(false)',
                 'owner.isAppRunning',
                 'owner.scarletRemoteContentReady()',
                 'UIApplication.didBecomeActiveNotification',
                 'stack?.restoreForegroundOnHostActive()',
                 'no_resign_no_process_restart'):
   self.assertIn(needle,SCENE)
  self.assertIn('fullscreen_scene_presenter_attached',SCENE)
  self.assertIn('content_ready_visibility_not_verified',SCENE)
 def test_no_global_swizzles_and_original_pan_preserved(self):
  self.assertIn('ScarletSceneGeometryAuthority.h',BRIDGE)
  for bad in ('hook_scarletGuestSendEvent','ScarletGuestRootSafeAreaOverride'):
   self.assertNotIn(bad,BRIDGE)
  drag=PAN[PAN.index('// UIkit pan tracks finger'):PAN.index('@objc(ScarletFullscreenGuestTabInstaller)')]
  move=PAN[PAN.index('    private static func panChanged('):PAN.index('    private static func resizeOverlay(')]
  self.assertEqual(hashlib.sha256(drag.encode()).hexdigest(),'105c875b0c09a1c6b567859da3ee1e273a3fb32e471f75b026bcdff4af561ff2')
  self.assertEqual(hashlib.sha256(move.encode()).hexdigest(),'37aaf834d19592d3846786abc794dac6365dc19fc9bdc96213251095555c24ce')
 def test_separate_release(self):
  self.assertIn('scarlet-v48-r5-recovery-r4-unsigned-20261111',FLOW)
  self.assertIn('scarlet-v48-r5-recovery-r5-unsigned-20261111',FLOW)
  self.assertIn('Scarlet-Crystal-V48-R5-RECOVERY-R5-UNSIGNED.ipa',FLOW)
if __name__=='__main__': unittest.main()
