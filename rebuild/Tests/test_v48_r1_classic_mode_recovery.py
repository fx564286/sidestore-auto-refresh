"""V48-R1 source regressions: pilot OFF cannot shadow original LC host.
Source tests only; native screen and actual iPhone app state need device verification.
"""
import unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
STACK=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
TAB=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
WORKFLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class TestV48RestoredNativeOff(unittest.TestCase):
 def test_off_does_not_mount_experimental_swiftui_geometry(self):
  self.assertIn('if experimentalFullscreenResident || fullscreenStack.hasResidentSession {',HOST)
  self.assertIn('ScarletFullscreenSceneViewportRepresentable(',HOST)
  self.assertIn('try await app.runApp(multitask: false)',HOST)
  self.assertIn('v48_original_launch_mode_selected',HOST)
  self.assertIn('"result": "classic_mode_after_pilot_disabled"',HOST)
  self.assertIn('experimentalFullscreenResident = false',HOST)
 def test_dead_ledger_rows_do_not_force_pilot_while_off(self):
  p=STACK[STACK.index('var hasResidentSession: Bool {'):STACK.index('var hasLiveResidentProcess: Bool {')]
  self.assertNotIn('!slots.isEmpty || pendingInPlaceLaunch',p)
  self.assertIn('if pendingInPlaceLaunch { return true }',p)
  self.assertIn('guard !slot.failed else { return false }',p)
  self.assertIn('viewport?.isAlive(folder: slot.id)',p)
  self.assertIn('return isVisible',p)
 def test_return_to_container_home_without_current_guest_identity(self):
  p=TAB[TAB.index('onExit: {',TAB.index('let content = ScarletFullscreenGuestFloatingTab(')):]
  self.assertIn('if let activeGuestFolder {',p)
  self.assertNotIn('guard let activeGuestFolder else',p)
  self.assertIn('defaults.set("ui", forKey: "selected")',p)
  self.assertIn('defaults.removeObject(forKey: "selectedContainer")',p)
  self.assertIn('LCSharedUtils.launchToGuestApp(withClassicMode: 0)',p)
  self.assertIn('return_to_host_bootstrap_requested',p)
  self.assertIn('return_to_host_without_guest_identity',p)
 def test_preserve_existing_bundle_and_no_data_removal(self):
  self.assertNotIn('revokeCertificate(',STACK)
  self.assertNotIn('removePersistentDomain(',TAB)
  self.assertNotIn('removePersistentDomain(',HOST)
  self.assertIn('scarlet-v48-r1-unsigned-20261111',WORKFLOW)
  self.assertIn('Scarlet-Crystal-V48-R1-UNSIGNED.ipa',WORKFLOW)
if __name__=='__main__':unittest.main()
