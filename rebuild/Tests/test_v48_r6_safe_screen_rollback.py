"""Root-cause ablation: keep V48-R5 proven outside-dismiss, undo unsafe guest mutations.
These tests protect source behavior, not optical verification on an iPhone.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
STACK=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
TAB=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
DIAG=(R/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class V48R6IsolatedAbalation(unittest.TestCase):
 def test_outside_shield_state_machine_kept_exactly(self):
  self.assertIn('private final class ScarletSwitcherOutsideShield: UIControl',TAB)
  self.assertIn('bringSubviewToFront(shield)',TAB)
  self.assertIn('dismissState?.requestClose()',TAB)
  self.assertIn('.onChange(of: dismissState.closeGeneration)',TAB)
  self.assertIn('closePanel() // Original V48 closePanel and button remain.',TAB)
  self.assertEqual(TAB.count('overlay.enableNativeOutsideDismiss()'),2)
 def test_guest_uses_original_immutable_ui_scene_during_boot(self):
  self.assertIn('private func observeAttachedGuestSurfaces',STACK)
  self.assertNotIn('controller.additionalSafeAreaInsets',STACK)
  self.assertNotIn('synchronizeAttachedGuestSafeAreas',STACK)
  self.assertNotIn('appliedRemoteInsets',STACK)
  self.assertIn('guest_remote_surface_probe',STACK)
  self.assertIn('view.bringSubviewToFront(target.view)',STACK)
  self.assertIn('vc.view.layer.opacity = key == folder ? 1 : 0',STACK)
 def test_diagnostic_fields_are_allowed(self):
  for k in ('guest_view_attached','guest_running','guest_view_width_pt','guest_view_height_pt'):
   self.assertIn('"'+k+'"',DIAG)
 def test_preserves_v48_and_release_identity(self):
  self.assertIn('ScarletGuestScreenPan(onChange: traceOriginalPan)',TAB)
  self.assertIn('private static func panChanged(',TAB)
  self.assertIn('Scarlet-Crystal-V48-R6-UNSIGNED.ipa',W)
  self.assertIn('scarlet-v48-r6-unsigned-20261111',W)
if __name__=='__main__':unittest.main()
