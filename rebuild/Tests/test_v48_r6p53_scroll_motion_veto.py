"""P53 on-device evidence: moving scroll-owned content cannot authorize a whole-scene crop."""
import unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
STACK=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
HOST=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
CI=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class P53ScrolledControls(unittest.TestCase):
 def test_second_sample_scroll_owner_gate_precedes_static_first_y_filter(self):
  f=STACK.split('private func onUnsafeGuestControls(',1)[1].split('private func onNativeHeaderTransform(',1)[0]
  self.assertIn('if sample == 2600, unsafe >= 3, top >= 20, top <= 130,',f)
  self.assertIn('let initial = chromeFirstUnsafeSampleByPID[pid]',f)
  self.assertIn('let scroll = chromeFirstScrollRiskByPID[pid]',f)
  self.assertIn('abs(initial.top - top) <= 3',f)
  self.assertIn('scroll.inScroll > 0, scroll.outside == 0',f)
  self.assertIn('inScroll == unsafe, outsideScroll == 0',f)
  self.assertIn('(first < -3 || abs(initial.first - first) > 16)',f)
  self.assertLess(f.index('guest_chrome_scroll_motion_crop_veto_armed'),f.index('first >= -3 && first < top - 15'))
  self.assertIn('controllers.values.contains(where: { $0.pid == pid && $0.isAppRunning })',f)
 def test_p52_actual_measured_scroll_protects_but_safe_guest_is_not_shielded(self):
  def early_gate(firstY,secondY,firstScroll,firstOutside,secondScroll,secondOutside,secondUnsafe,topA=62,topB=62):
   return (secondUnsafe>=3 and 20<=topB<=130 and abs(topA-topB)<=3 and
    firstScroll>0 and firstOutside==0 and secondScroll==secondUnsafe and
    secondOutside==0 and (secondY<-3 or abs(firstY-secondY)>16))
  self.assertTrue(early_gate(3,-21,8,0,5,0,5))
  self.assertFalse(early_gate(3,-21,8,1,5,0,5))
  self.assertFalse(early_gate(3,-21,8,0,4,1,5))
  self.assertFalse(early_gate(3,-21,0,0,0,0,0))
  self.assertFalse(early_gate(3,-21,8,0,5,0,5,62,40))
 def test_full_fbscene_crop_prohibited_before_independent_freshness(self):
  b=STACK.split('private func applyP43FallbackChrome(',1)[1].split('func setResidentOutsideDismissEnabled(',1)[0]
  self.assertLess(b.index('guard !chromeScrollCropVetoPIDs.contains(pid)'),b.index('guard chromeFreshUnsafeProofPIDs.contains(pid)'))
  self.assertLess(b.index('guard chromeFreshUnsafeProofPIDs.contains(pid)'),b.index('chromeEligiblePIDs.insert(pid)'))
  self.assertIn('guest_chrome_scroll_surface_crop_withheld',b)
  self.assertIn('let top = reserved ? chromeTop(in: scene) : 0',STACK)
  self.assertIn('let rect = contentSlot(in: scene, reserved: reserved)',STACK)
 def test_no_theme_or_guest_userstate_changes_and_isolated_release(self):
  self.assertNotIn('.preferredColorScheme(',HOST)
  self.assertIn('nativeStatusBarCollisionShield',HOST)
  self.assertIn('chromeScrollCropVetoPIDs.remove(old.pid)',STACK)
  self.assertIn('fix/scarlet-v48-r6p53-scroll-motion-crop-veto-20261113',CI)
  self.assertIn('scarlet-v48-r6p53-scroll-motion-unsigned-20261113',CI)
  self.assertIn('Scarlet-Crystal-V48-R6P53-SCROLL-MOTION-UNSIGNED.ipa',CI)
if __name__=='__main__':unittest.main()
