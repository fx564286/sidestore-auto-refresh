"""P74: signed P71 8 -> 5 controls (y3->y60, safeTop62) should not hide clock forever.

Native source contracts + concrete regression scenarios; device imagery still required.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
G=(R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
H=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
D=(R/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class TwoStageStrictNearStatusband(unittest.TestCase):
 def test_scans_full_actual_visible_view_hierarchy_without_mutations(self):
  p=G.split('// R6P74_STATUSBAND_EVIDENCE_BEGIN',1)[1].split('// R6P74_STATUSBAND_EVIDENCE_END',1)[0]
  for x in ('ScarletIslandVisibleFrameInWindow(node,window)',
   'depth>56', 'risk->visited>2400', 'risk->capped=YES',
   'CGRectGetMinY(visible)', 'y<safeTop-9', 'risk->severeNodes++',
   'risk->nearControls++', 'risk->firstNearControlY',
   'window.rootViewController!=root',
   'UISceneActivationStateForegroundActive',
   'fabs(root.view.safeAreaInsets.top-safeTop)>3',
   '@"guest_post_header_statusband_probe"'):
   self.assertIn(x,p,x)
  for forbidden in ('node.frame=', 'window.frame=', 'root.frame=',
    'contentInset =', 'contentOffset =', 'setStatusBarHidden',
    'transform =', 'setFrame(', 'method_exchangeImplementations('):
   self.assertNotIn(forbidden,p)
  self.assertIn('for(NSNumber *late in @[@2850, @3550])',G)
  self.assertIn('ScarletP74ScheduleStatusbandProbes(window, expectedTop);',G)
  self.assertIn('for(NSNumber *delay in @[@650, @2600])',G)
  self.assertEqual(G.count('ScarletP74PublishStatusband(w,r,expectedTop,sample);'),1)
 def test_release_only_for_2_complete_full_depth_scan_after_verified_header(self):
  p=H.split('func acceptVerifiedPostHeaderStatusband(',1)[1].split('// R6P56:',1)[0]
  for x in ('sample == 2850 || sample == 3550',
   'scene.interfaceOrientation.isPortrait', 'headerVerified && complete',
   'severe == 0', 'near > 0', '(40...130).contains(safeTop)',
   'firstNearY >= safeTop - 9 && firstNearY <= safeTop - 2',
   'nativeStatusBarUnsafePIDs.contains(pid)',
   'nativeStatusBandFirstPassPIDs.insert(pid)',
   'guard nativeStatusBandFirstPassPIDs.remove(pid) != nil else { return }',
   'nativeStatusBarUnsafePIDs.remove(pid)',
   'nativeStatusBarSafePIDs.insert(pid)',
   'nativeStatusBarCollisionShield = false',
   'status_hidden', 'two_complete_near_boundary_proofs_status_released'):
   self.assertIn(x,p,x)
  self.assertLess(p.index('guard nativeStatusBandFirstPassPIDs.remove(pid)'),
                  p.index('nativeStatusBarCollisionShield = false'))
  self.assertIn('nativeStatusBandFirstPassPIDs.remove(pid)',
   H.split('func clearNativeStatusBarCollisionRisk(pid: Int32)',1)[1][:200])
 def test_guest_receipt_host_wire_is_same_pid_and_header_source(self):
  self.assertIn('onPostHeaderStatusbandMeasured',H)
  self.assertIn('self.chromeHeaderProtectedPIDs.contains(pid)',H)
  self.assertIn('result == "guest_post_header_statusband_probe"',H)
  for field in ('near_controls','severe_nodes','scan_complete','first_near_control_y'):
   self.assertIn('"'+field+'"',D)
 def test_p71_signed_device_boundary_and_real_severe_fail_closed(self):
  # Scenario predicate mirrors exact native condition, not a passing device test.
  def eligible(top, first, near, severe, complete, header):
   return header and complete and severe==0 and near>0 and (40<=top<=130) and top-9<=first<=top-2
  self.assertFalse(eligible(62,3,8,7,True,False))  # 650ms actual P71
  self.assertTrue(eligible(62,60,5,0,True,True))  # 2600ms after actual header
  self.assertFalse(eligible(62,60,5,1,True,True))
  self.assertFalse(eligible(62,60,5,0,False,True))
  self.assertFalse(eligible(62,60,5,0,True,False))
  self.assertFalse(eligible(62,40,5,0,True,True))
  self.assertFalse(eligible(0,0,0,0,True,True))
 def test_versioned_build(self):
  for x in ('fix/scarlet-v48-r6p74-statusband-proof-20261115',
    '--host-build-version 3.8.74',
    'Scarlet-Crystal-V48-R6P74-STATUSBAND-PROOF-UNSIGNED.ipa',
    'scarlet-v48-r6p74-statusband-proof-unsigned-20261115'):
   self.assertIn(x,W)
if __name__=='__main__':unittest.main()
