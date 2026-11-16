"""P83 single status visibility policy for host+resident floating UIWindow.
This statically verifies code ownership, not visual iPhone statusbar success.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
STACK=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
OVERLAY=(R/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
WF=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class P83SingleStatusOwner(unittest.TestCase):
 def test_only_host_root_sets_swiftui_hidden_preference(self):
  self.assertEqual(HOST.count('.statusBarHidden(fullscreenStack.isVisible &&'),1)
  self.assertIn('nativeStatusBarCollisionShield',HOST)
  self.assertNotIn('.preferredColorScheme(',HOST)
  self.assertIn('.ignoresSafeArea(.all, edges: .all)',HOST)
 def test_overlay_does_not_force_visible_statusbar_against_host(self):
  self.assertIn('var residentBarHidden: Bool = false',OVERLAY)
  self.assertIn('override var prefersStatusBarHidden: Bool { residentBarHidden }',OVERLAY)
  self.assertNotIn('override var prefersStatusBarHidden: Bool { false }',OVERLAY)
  self.assertIn('owner.residentBarHidden = hidden',OVERLAY)
  self.assertIn('static func syncResidentStatusBarHidden(_ hidden: Bool, scene: UIWindowScene)',OVERLAY)
  self.assertIn('window.residentHostOwnsOutsideTaps',OVERLAY)
 def test_native_writers_share_exact_per_pid_shield(self):
  self.assertEqual(STACK.count('hidden: stack?.nativeStatusBarCollisionShield == true'),2)
  self.assertIn('syncResidentStatusBarHidden(\n                shield, scene: scene)',STACK)
  self.assertIn('syncResidentStatusBarHidden(\n            false, scene: scene)',STACK)
  self.assertIn('stack.nativeStatusBarCollisionShield, scene: scene)',STACK)
  self.assertIn('nativeStatusBarUnsafePIDs.insert(pid)',STACK)
  self.assertIn('nativeStatusBandFirstPassPIDs.insert(pid)',STACK)
 def test_device_risk_not_declared_fixed_or_shielded_unconditionally(self):
  self.assertIn('ScarletIslandP77TrySevereNestedContent',
    (R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text())
  self.assertIn('reportNativeStatusBarCollisionRisk(pid:',STACK)
  self.assertIn('nativeStatusBarCollisionShield = false',STACK)
  self.assertNotIn('window.frame = CGRect(x:0,y:62',STACK)
  self.assertNotIn('nativeStatusBarCollisionShield = false\n        nativeStatusBarUnsafePIDs.insert(pid)',STACK)
 def test_release_identity(self):
  for x in ('fix/scarlet-v48-r6p83-single-statusbar-authority-20261116',
            '--host-build-version 3.8.83',
            'Scarlet-Crystal-V48-R6P83-STATUSBAR-OWNER-UNSIGNED.ipa',
            'scarlet-v48-r6p83-statusbar-owner-unsigned-20261116',
            '"r6p83"'):
   self.assertIn(x,WF)

if __name__=='__main__':unittest.main()
