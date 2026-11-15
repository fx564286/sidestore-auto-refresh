"""P77: P76 mixed y50 severe + y60 near scroll owners are mutually exclusive."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
G=(R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
P=G.split('// R6P77_SEVERE_SPLIT_OWNER_NATIVE_CONTENT_BEGIN',1)[1].split('// R6P77_SEVERE_SPLIT_OWNER_NATIVE_CONTENT_END',1)[0]
class P77ActualDeviceFailureFix(unittest.TestCase):
 def test_actual_p76_signed_cohort_rejected_by_old_and_routed_to_p77(self):
  # PID754 safeTop62 severe50 and five near59.5: the P76 all-risk y<55
  # condition is impossible to satisfy; split-owner gating is essential.
  safe=62; ys=[50,59.5,59.5,59.5,59.5,59.5]
  self.assertFalse(all(safe-20<=y<safe-7 for y in ys))
  severe=[y for y in ys if safe-18<=y<safe-9]
  near=[y for y in ys if safe-9<=y<safe-2]
  self.assertEqual((len(severe),len(near)),(1,5))
  self.assertEqual(__import__('math').ceil(safe-min(severe)+2),14)
  self.assertIn('if(y>=top-18 && y<top-9)',P)
  self.assertIn('else if(y>=top-9 && y<top-2)',P)
  self.assertIn('severe.count<1 || severe.count>2 || near.count<3',P)
 def test_near_controls_must_be_outside_severe_owner(self):
  for x in ('ScarletIslandP60GatherRiskControls(root,header,w,top,0',
            'if(v==scroll || [v isDescendantOfView:scroll])',
            'if(nearHere || !scroll.scrollEnabled',
            'fabs(scroll.contentOffset.y+inset)>3',
            'inset<top-22 || inset>top+8',
            'fabs(scroll.zoomScale-1)>0.01'):
   self.assertIn(x,P,x)
 def test_runtime_inset_delta_is_reversible_without_guest_frame_edits(self):
  for x in ('applied.top+=delta;',
            'scroll.contentInset=applied;',
            'scroll.contentOffset=CGPointMake(oldOffset.x,oldOffset.y-delta)',
            'CGRectEqualToRect(sc.frame,oldFrame)',
            'CGSizeEqualToSize(sc.contentSize,oldContent)',
            'band.severeNodes==0',
            'band.firstNearControlY>=safeTop-9',
            'sc.contentInset=oldInset;',
            'sc.contentOffset=CGPointMake(live.x,live.y+delta)',
            'state[@"p77_proven"]=@YES;',
            'p77_severe_nested_content_zero_collision',
            'p77_severe_native_scroll_rolled_back'):
   self.assertIn(x,P,x)
  for x in ('scroll.frame=', 'scroll.transform=', 'root.frame=',
            'window.frame=', 'scroll.contentSize=',
            'setStatusBarHidden', 'statusBarHidden='):
   self.assertNotIn(x,P,x)
 def test_only_after_verified_header_and_failed_p76_selection(self):
  self.assertIn('if(reduced && late) {',G)
  self.assertIn('ScarletIslandP76TryPostHeaderContentOrigin(w,vc,safeTop);',G)
  self.assertIn('ScarletIslandP77TrySevereNestedContent(w,vc,safeTop);',G)
  self.assertIn('[state[@"p76_attempted"] boolValue]',P)
  self.assertIn('[state[@"body_disabled"] boolValue]',P)
  self.assertIn('for(NSNumber *late in @[@2850, @3550])',G)
 def test_preserve_base_p76_and_build_p77(self):
  for x in ('--host-build-version 3.8.77',
            '"r6p77"',
            'Scarlet-Crystal-V48-R6P77-SEVERE-SCROLL-UNSIGNED.ipa',
            'scarlet-v48-r6p77-severe-scroll-unsigned-20261116'):
   self.assertIn(x,W)
if __name__=='__main__': unittest.main()
