"""Recovery contract for V48-R5 after verified R5V 9/9 guest terminations.
Source tests cannot replace device process-liveness or fatal .ips stack.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
GLUE=(R/'integration/apply_scarlet_host.py').read_text()
SWITCH=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
WORKFLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class StableGuestRecovery(unittest.TestCase):
 def test_no_experimental_global_guest_hooks(self):
  for unexpected in ('hook_scarletGuestSendEvent:',
      'ScarletGuestRootSafeAreaOverride', 'ScarletGuestInstallRootSafeAreaGetter',
      'ScarletGuestOutsideDarwinBridge', 'GuestRootSafeArea.Enabled.V1',
      'safearea_root_window_timeout'):
   self.assertNotIn(unexpected,GLUE)
   self.assertNotIn(unexpected,SWITCH)
  self.assertIn('ScarletGuestScreenPan(onChange: traceOriginalPan)',SWITCH)
  self.assertIn('private static func panChanged(',SWITCH)
 def test_host_lifecycle_observation_not_mutation(self):
  self.assertIn('guestProcessStartTimes[ObjectIdentifier(vc)] = Date()',HOST)
  self.assertIn('duration_ms',HOST)
  self.assertIn('native_exit_callback_no_ips_reason',HOST)
  self.assertIn('source": "original_LC_scene_delegate',HOST)
  self.assertIn('fullscreen_scene_process_exited',HOST)
 def test_separate_recovery_ipa_release(self):
  self.assertIn('scarlet-v48-r5-recovery-unsigned-20261111',WORKFLOW)
  self.assertIn('Scarlet-Crystal-V48-R5-RECOVERY-UNSIGNED.ipa',WORKFLOW)
if __name__=='__main__': unittest.main()
