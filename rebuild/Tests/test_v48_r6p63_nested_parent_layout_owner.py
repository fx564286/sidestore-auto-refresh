"""P63: scope the P62 nested-scroll reflow to the actual parent layout completion."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
S=(R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
P=S.split('// R6P63_NESTED_LAYOUT_OWNER_BEGIN',1)[1].split('// R6P63_NESTED_LAYOUT_OWNER_END',1)[0]
O=S.split('// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN',1)[1].split('// R6P54_OWNER_LAYOUT_CONTRACT_END',1)[0]
class P63NestedParent(unittest.TestCase):
 def test_actual_parent_layout_after_original_method_and_per_instance(self):
  for x in ('ScarletIslandP63BindNestedParent','ScarletIslandP63MaintainNestedViewport',
    'ScarletIslandP63UnbindNestedParent','@selector(layoutSubviews)',
    '((void (*)(id,SEL))originalIMP)(receiver,selector);',
    'ScarletIslandP63MaintainNestedViewport(receiver);',
    'objc_setAssociatedObject(parent,&scarletIslandP63NestedParentLayoutKey',
    'object_setClass(parent,scoped)', 'scroll.superview!=parent',
    'window.windowScene.activationState!=UISceneActivationStateForegroundActive',
    'revised.origin.y+=delta','revised.size.height-=delta'):
   self.assertIn(x,P,x)
  self.assertNotIn('method_exchangeImplementations',P)
 def test_dock_only_after_identified_parent_own_layout_and_support_rollback(self):
  for x in ('ScarletIslandP63BindNestedParent(\n            p60DeepScroll.superview,state)',
   '[p60DeepScroll.superview layoutIfNeeded]',
   'ScarletIslandP63MaintainNestedViewport(p60DeepScroll.superview)',
   'ScarletIslandP63UnbindNestedParent(bodyParent,state)',
   'focusedComplete && focusedUnsafe==0 && scrollStateUnchanged',
   'bodyTrial && feed.superview==bodyParent',
   'feed.frame=oldFeed;','native_status','state[@"body_disabled"]=@YES;'):
   if x=='native_status': continue
   self.assertIn(x,O,x)
  self.assertIn('ScarletIslandP63UnbindNestedParent(bodyParent,state);',O)
 def test_native_offset_reconciles_only_within_bound_and_content_unchanged(self):
  for x in ('CGSizeEqualToSize(sc.contentSize','isfinite(sc.contentOffset.y)',
    'sc.contentOffset.y>=-sc.adjustedContentInset.top-4',
    'sc.contentSize.height-CGRectGetHeight(sc.bounds)',
    'UIEdgeInsetsEqualToEdgeInsets(sc.contentInset'):
   self.assertIn(x,O,x)
  self.assertNotIn('CGPointEqualToPoint(sc.contentOffset',O)
 def test_build_identity(self):
  for x in ('fix/scarlet-v48-r6p63-nested-parent-20261114',
    'SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.63)',
    'Scarlet-Crystal-V48-R6P63-NESTED-PARENT-UNSIGNED.ipa',
    'scarlet-v48-r6p63-nested-parent-unsigned-20261114'):
   self.assertIn(x,W,x)
if __name__=='__main__': unittest.main()
