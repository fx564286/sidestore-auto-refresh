"""P51 status icon overlap containment; does not prove a visual layout repair."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
H=(ROOT/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
UI=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
WF=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class P51NativeCollisionShield(unittest.TestCase):
 def test_risky_guest_shield_sticky_after_second_zero_sample(self):
  method=H.split('func reportNativeStatusBarCollisionRisk(',1)[1].split('func clearNativeStatusBarCollisionRisk(',1)[0]
  self.assertIn('if unsafe > 0 {',method)
  self.assertIn('nativeStatusBarUnsafePIDs.insert(pid)',method)
  self.assertIn('else if !nativeStatusBarUnsafePIDs.contains(pid)',method)
  self.assertIn('nativeStatusBarUnsafePIDs.contains(pid) ||',method)
  self.assertIn('nativeStatusBarCollisionShield = shield',method)
  self.assertIn('resident_native_status_bar_collision_readback',method)
  self.assertIn('scene.statusBarManager?.isStatusBarHidden',method)
 def test_host_real_statusbar_hidden_not_guest_geometry(self):
  self.assertEqual(UI.count('.statusBarHidden(fullscreenStack.isVisible &&'),2)
  self.assertIn('fullscreenStack.nativeStatusBarCollisionShield',UI)
  self.assertIn('!fullscreenStack.nativeStatusBarCollisionShield',UI)
  self.assertIn('let top = reserved ? chromeTop(in: scene) : 0',H)
  self.assertIn('chromeScrollCropVetoPIDs.contains(pid)',H)
  self.assertIn('hostStatusBarScheme = next',H)
  self.assertNotIn('UIDevice.current.batteryLevel',UI)
 def test_unknown_guest_avoids_flash_and_home_restores_status(self):
  enqueue=H.split('func enqueueSignedGuest(',1)[1].split('func attach(',1)[0]
  self.assertIn('nativeStatusBarCollisionShield = true',enqueue)
  home=H.split('func goHome()',1)[1].split('private func recoverFastFailedGuest(',1)[0]
  self.assertIn('nativeStatusBarCollisionShield = false',home)
  activate=H.split('func activate(folder:',1)[1].split('func reportNativeStatusBarCollisionRisk(',1)[0]
  self.assertIn('nativeStatusBarSafePIDs.contains(slot.pid)',activate)
  self.assertIn('nativeStatusBarUnsafePIDs.contains(slot.pid)',activate)
  self.assertIn('nativeStatusBarCollisionShield = wasShielded',activate)
  self.assertIn('stack?.clearNativeStatusBarCollisionRisk(pid: old.pid)',H)
 def test_measurement_only_existing_telemetry_and_p51_release(self):
  self.assertIn('self.stack?.reportNativeStatusBarCollisionRisk(',H)
  self.assertIn('self.onUnsafeGuestControls(pid: pid, unsafe: unsafe,',H)
  self.assertIn('scarlet-v48-r6p51-status-collision-shield-unsigned-20261113',WF)
  self.assertIn('Scarlet-Crystal-V48-R6P51-STATUS-COLLISION-SHIELD-UNSIGNED.ipa',WF)
if __name__=='__main__':unittest.main()
