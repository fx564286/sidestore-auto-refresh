"""P60: separately identified nested scroll owner, not P56/59 guessed sibling."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
G=(R/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
W=(R.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
P=G.split("// R6P60_COMMON_SCROLL_ANCESTOR_BEGIN",1)[1].split("// R6P60_COMMON_SCROLL_ANCESTOR_END",1)[0]
O=G.split("// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN",1)[1].split("// R6P54_OWNER_LAYOUT_CONTRACT_END",1)[0]

class P60NestedOwner(unittest.TestCase):
    def test_bounded_nested_proof_avoids_p59_24_level_truncation(self):
        for x in ("depth>56","++(*visited)>2400","ScarletIslandP60GatherRiskControls(",
                  "ScarletIslandVisibleFrameInWindow(view,window)",
                  "NSMutableArray<UIView *> *risk","if(capped || risk.count<3 || risk.count>32)",
                  "if(node!=scroll && ![node isDescendantOfView:scroll])",
                  "cursor==p56Body","scroll.contentSize.height<h+safeTop+25"):
            self.assertIn(x,P,x)
    def test_native_scroll_segment_not_global_inset_or_resize(self):
        for x in ('ScarletIslandP60CommonUnsafeScroll(',
                  'UIView *nativeBody=p60DeepScroll ? (UIView *)p60DeepScroll : p59Body;',
                  '@"body_kind":@(p60DeepScroll ? 60 : 59)',
                  'revised.origin.y+=delta;', 'revised.size.height-=delta;',
                  'scroll.contentSize.height>=',
                  'CGRectGetHeight(originalBody)+delta+20',
                  'fabs(CGRectGetMaxY(revised)-CGRectGetMaxY(originalBody))<1',
                  'body.frame=revised;'):
            self.assertIn(x,O,x)
        for forbidden in ("window.frame=","root.frame=","contentInset=",
                          "contentOffset=","method_exchangeImplementations"):
            self.assertNotIn(forbidden,P,forbidden)
    def test_two_step_real_risk_and_scroll_preservation_readback(self):
        for x in ('ScarletIslandP60FocusedUnsafe(rt,w,safeTop,&focusedComplete)',
                  'focusedComplete && focusedUnsafe==0 && scrollStateUnchanged',
                  'CGSizeEqualToSize(sc.contentSize',
                  'CGPointEqualToPoint(sc.contentOffset',
                  'UIEdgeInsetsEqualToEdgeInsets(sc.contentInset',
                  'BOOL provenBody=bodyTrial && feed.superview==bodyParent',
                  'unsafe==0;', 'feed.frame=oldFeed;',
                  'guest_owner_content_reflow_retained','guest_owner_content_reflow_reverted',
                  '(int64_t)1100*NSEC_PER_MSEC'):
            self.assertIn(x,O,x)
    def test_rotation_restores_deep_scroll_viewport_before_legacy_early_return(self):
        a=O.index('!UIInterfaceOrientationIsPortrait(window.windowScene.interfaceOrientation)) {')
        b=O.index('if(!header || !window || window.hidden')
        self.assertLess(a,b)
        self.assertIn('scroll.frame=[state[@"body_original_frame"] CGRectValue]',O)
        self.assertIn('state[@"body_disabled"]=@YES;',O)
    def test_ci_unique_install_identity(self):
        for x in ('fix/scarlet-v48-r6p60-deep-owner-20261114',
                  'SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.60)',
                  'scarlet-v48-r6p60-deep-owner-unsigned-20261114',
                  'Scarlet-Crystal-V48-R6P60-DEEP-OWNER-UNSIGNED.ipa'):
            self.assertIn(x,W,x)

if __name__=="__main__":unittest.main()
