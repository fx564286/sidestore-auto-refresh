"""R5X source contracts: iOS guest root owns content layout, original R5 stays available.
These checks do NOT demonstrate iPhone optical correction or launch-speed gain.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
STACK=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
GLUE=(R/'integration/apply_scarlet_host.py').read_text()
UI=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class AlternativeGuestRootSafeArea(unittest.TestCase):
 def test_nonzero_host_safearea_shared_with_guest(self):
  self.assertIn('publishPilotGuestRootSafeArea(_ scene: UIWindowScene)',STACK)
  self.assertIn('if scene.interfaceOrientation.isPortrait && top < 20 { return }',STACK)
  self.assertIn('Scarlet.Pilot.GuestRootSafeArea.Enabled.V1',STACK)
  self.assertIn('Scarlet.Pilot.GuestRootSafeArea.TopPoints.V1',STACK)
  self.assertIn('shared.set(Double(top), forKey:',STACK)
  self.assertIn('pilot_guest_root_safearea_published',STACK)
  self.assertIn('UserDefaults.lc()?.bool(forKey: "Scarlet.Pilot.LegacyHostInsetsFallback.V1") == true',STACK)
 def test_guest_root_uses_safe_layout_not_geometry_or_remote_fbscene(self):
  for fragment in ('ScarletGuestTryApplyRootSafeArea(void)',
       'ScarletGuestInstallRootSafeAreaObserver(void)',
       'NSUserDefaults.isLiveProcess',
       'root.additionalSafeAreaInsets = extra;',
       'root.view.safeAreaInsets.top',
       'UIWindowDidBecomeVisibleNotification',
       'UISceneDidActivateNotification',
       'safearea_root_adjusted',
       'safearea_root_already_correct',
       'ScarletGuestRootBaselineTopKey',
       'ScarletGuestRootAppliedTopKey'):
   self.assertIn(fragment,GLUE)
  self.assertIn('unmodified_passthrough_guest_root_inset',GLUE)
  self.assertIn('[self hook__performUpdateWithoutActivation:updateBlock];',GLUE)
  self.assertIn('if(!NSUserDefaults.lcGuestAppId) return;',GLUE)
  self.assertIn('safearea_root_pilot_disabled',GLUE)
  self.assertNotIn('root.view.frame =',GLUE)
 def test_protected_existing_v48_r5_touch_geometry(self):
  self.assertIn('private final class ScarletSwitcherOutsideShield: UIControl',UI)
  self.assertIn('dismissState?.requestClose()',UI)
  self.assertIn('ScarletGuestScreenPan(onChange: traceOriginalPan)',UI)
  self.assertIn('private static func panChanged(',UI)
  self.assertIn('vc.scaleRatio = 1',STACK)
 def test_original_r5_release_and_experimental_build_coexist(self):
  self.assertIn('scarlet-v48-r5-unsigned-20261111',W)
  self.assertIn('scarlet-v48-r5x-unsigned-20261111',W)
  self.assertIn('Scarlet-Crystal-V48-R5X-UNSIGNED.ipa',W)
if __name__=='__main__':unittest.main()
