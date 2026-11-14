"""P65: repair blocked P64 binder and avoid native-inset double compensation."""
from pathlib import Path
import unittest,ast
R=Path(__file__).resolve().parents[1]
S=(R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
P=S.split('// R6P65_SETTLED_NATIVE_INSET_COMPENSATION_BEGIN',1)[1].split('// R6P65_SETTLED_NATIVE_INSET_COMPENSATION_END',1)[0]
N=S.split('// R6P63_NESTED_LAYOUT_OWNER_BEGIN',1)[1].split('// R6P63_NESTED_LAYOUT_OWNER_END',1)[0]
O=S.split('// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN',1)[1].split('// R6P54_OWNER_LAYOUT_CONTRACT_END',1)[0]
C=S.split('static void ScarletIslandContentProbe(',1)[1].split('// R6P37 distinct',1)[0]
class P65(unittest.TestCase):
 def test_p64_actual_binder_repair_and_p65_are_both_supported(self):
  for needle in ('(kind!=60 && kind!=64 && kind!=65)',
                 '[state[@"body_kind"] integerValue]==64 ||',
                 '[state[@"body_kind"] integerValue]==65',
                 'BOOL residual=kind==64;', 'CGFloat delta=kind==65 ?',
                 '[state[@"p65_native_top_inset"] doubleValue]'):
   self.assertIn(needle,N,needle)
 def test_fallback_only_after_actual_failed_body_and_at_measured_postload_sample(self):
  self.assertIn('ScarletIslandP65TrySettledNativeViewport(\n        window,expectedRoot,expectedTop,sample);',C)
  for needle in ('sample!=2600',
   '![state[@"body_disabled"] boolValue]',
   '[state[@"p65_attempted"] boolValue]',
   'newStable<2', 'settle(4,0)', '240*NSEC_PER_MSEC',
   'ScarletIslandP65ValidateSettled(scroll,nativeTop)',
   'scroll.dragging', 'scroll.decelerating',
   'fabs(scroll.contentOffset.y+nativeTop)<3'):
   self.assertIn(needle,P,needle)
 def test_new_math_compensates_existing_inset_and_preserves_bottom_and_no_inset_override(self):
  for native_inset in (50,58,62):
   header_bottom=112
   old_y=0
   old_height=956
   delta=header_bottom-old_y-native_inset
   self.assertGreaterEqual(delta,15)
   self.assertEqual(old_y+delta+native_inset,header_bottom)
   self.assertEqual((old_y+delta)+(old_height-delta),956)
  for needle in ('CGRectGetMaxY(headerRect)-',
   '(CGRectGetMinY(rect)+nativeTop)',
   'nativeTop<top-28', 'risk.count>3',
   'if(capped', 'fabs(CGRectGetMinY(rect))>5',
   'fabs(scroll.adjustedContentInset.top-nativeTop)<2'):
   self.assertIn(needle,P,needle)
  self.assertNotIn('scroll.contentInset =',P)
  self.assertNotIn('scroll.contentOffset =',P)
  self.assertNotIn('window.frame =',P)
  self.assertNotIn('additionalSafeAreaInsets =',P)
 def test_proof_is_real_2_pass_zero_and_rollback_before_native_icons(self):
  for needle in ('ScarletIslandP60FocusedUnsafe(r,ww,safeTop,&complete)',
   'ScarletIslandDeepHeaderCountUnsafe(r,ww,safeTop,&images)',
   'focused==0', 'unsafe==0 && images==0',
   'ScarletIslandP65ValidateSettled(sc,nativeTop)',
   'CGSizeEqualToSize(sc.contentSize',
   'UIEdgeInsetsEqualToEdgeInsets(sc.contentInset',
   'ScarletIslandP63UnbindNestedParent(par,state);',
   'sc.frame=originalFrame;',
   'guest_owner_content_reflow_retained',
   'guest_owner_content_reflow_reverted',
   'guest_owner_content_reflow_first_pass',
   '250*NSEC_PER_MSEC', '1000*NSEC_PER_MSEC'):
   self.assertIn(needle,P,needle)
  for needle in ('bodyKind==60 || bodyKind==64 || bodyKind==65',
   'delta=bodyKind==65 ?'):
   self.assertIn(needle,O,needle)
 def test_release(self):
  for needle in ('fix/scarlet-v48-r6p65-inset-compensated-settle-20261115',
   'SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.65)',
   'Scarlet-Crystal-V48-R6P65-SETTLED-INSET-UNSIGNED.ipa',
   'scarlet-v48-r6p65-settled-inset-unsigned-20261115',
   'version="3.8.65" if "r6p65"'):
   self.assertIn(needle,W)
  ast.parse(next(x for x in W.splitlines() if 'version="3.8.65"' in x).strip())
if __name__=="__main__":unittest.main()
