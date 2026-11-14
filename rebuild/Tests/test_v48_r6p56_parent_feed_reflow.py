"""Native parent header+feed reflow, zero-risk status release; P55 device grounded."""
import unittest
from pathlib import Path
D=Path(__file__).resolve().parents[1]
G=(D/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H=(D/"HostApp/ScarletFullscreenSceneStack.swift").read_text()
W=(D.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
B=G.split("// R6P56_OWNER_CONTENT_REFLOW_BEGIN",1)[1].split("// R6P56_OWNER_CONTENT_REFLOW_END",1)[0]
OWNER=G.split("// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN",1)[1].split("// R6P54_OWNER_LAYOUT_CONTRACT_END",1)[0]
class ParentFeedReflow(unittest.TestCase):
 def test_owns_one_fullwidth_real_scroll_body_not_scene_or_tabbar(self):
  for k in ('ScarletIslandP56UniqueNativeBody(', 'if(only) return nil;',
    'candidate.window!=window', 'candidate==header',
    'CGRectGetHeight(parent.bounds)', 'rect.size.height<height*0.65',
    'ScarletIslandP56ContainsFeedScroll(candidate,4)',
    '[candidate isKindOfClass:UITabBar.class]'):
   self.assertIn(k,B,k)
  for bad in ('window.frame=', 'root.frame=', 'scroll.contentInset=',
     'scroll.contentOffset=', 'method_exchangeImplementations('):
   self.assertNotIn(bad,B)
 def test_parent_after_native_reflows_sibling_and_preserves_bottom(self):
  for k in ('CGRectGetMaxY(header.frame)','revised.origin.y=desiredY',
    'revised.size.height-=delta','body.frame=revised',
    'CGRectGetMaxY(revised)-CGRectGetMaxY(originalBody)',
    'state[@"body_reflow_passes"]'):
   self.assertIn(k,OWNER,k)
 def test_two_real_zero_unsafe_readbacks_else_revert_only_body(self):
  for k in ('guest_owner_content_reflow_first_pass','guest_owner_content_reflow_retained',
    'guest_owner_content_reflow_reverted', 'unsafe==0', 'feed.frame=oldFeed',
    'state[@"body_disabled"]=@YES','(int64_t)1100*NSEC_PER_MSEC'):
   self.assertIn(k,OWNER,k)
 def test_reflow_receipt_cannot_succeed_before_original_parent_hit_gate(self):
  self.assertLess(OWNER.index('BOOL reduced=unchanged &&'),
                  OWNER.index('guest_owner_content_reflow_retained'))
  self.assertIn('BOOL bodyAccepted=provenBody && reduced;',OWNER)
  self.assertIn('late && bodyAccepted',OWNER)
 def test_status_bar_cannot_clear_for_single_transient_zero_or_p55_six(self):
  for k in ('onContentReflowVerified?(pid)','guest_owner_content_reflow_retained',
    'row["header_controls_after"] as? NSNumber)?.intValue == 0',
    'row["header_gate_pass"] as? NSNumber)?.boolValue == true',
    'func acceptVerifiedNativeContentReflow(pid: Int32',
    'nativeStatusBarUnsafePIDs.remove(pid)','nativeStatusBarSafePIDs.insert(pid)',
    'nativeStatusBarCollisionShield=false', 'guest_owner_layout_contract_retained'):
   self.assertIn(k,H,k)
  self.assertIn('scarlet-v48-r6p56-native-feed-unsigned-20261114',W)
if __name__=="__main__":unittest.main()
