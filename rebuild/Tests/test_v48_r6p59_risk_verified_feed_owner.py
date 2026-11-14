"""P59: Select only the native scroll sibling demonstrably owning residual unsafe controls."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
G=(ROOT/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
W=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
BLOCK=G.split("// R6P59_RESIDUAL_UNSAFE_OWNER_BEGIN",1)[1].split("// R6P59_RESIDUAL_UNSAFE_OWNER_END",1)[0]
OWNER=G.split("// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN",1)[1].split("// R6P54_OWNER_LAYOUT_CONTRACT_END",1)[0]

class R6P59RiskVerifiedOwner(unittest.TestCase):
    def test_causal_difference_from_p56_geometry_only_candidate(self):
        for marker in (
            "ScarletIslandP59VisibleRiskInSubtree(",
            "ScarletIslandWalkViews(view,window,safeTop,0,&m,scrollOwners)",
            "return m.visibleUnsafeControls;",
            "NSUInteger headerRisk=ScarletIslandP59VisibleRiskInSubtree(",
            "NSUInteger residual=totalBefore-headerRisk;",
            "NSUInteger risk=ScarletIslandP59VisibleRiskInSubtree(",
            "if(risk!=residual || only) return nil;",
            "return only && only!=p56Body ? only : nil;"):
            self.assertIn(marker,BLOCK,marker)
        self.assertIn("ScarletIslandP56UniqueNativeBody(parent,header,window)",OWNER)
        self.assertIn("ScarletIslandP59UniqueRiskNativeBody(",OWNER)
    def test_preserves_safety_on_unknown_or_multiple_scroll_owners(self):
        for marker in (
            "if(m.capped) return NSUIntegerMax;",
            "if(risk==NSUIntegerMax) return nil;",
            "if(headerRisk==NSUIntegerMax || headerRisk<2 ||",
            "if(risk!=residual || only) return nil;",
            "candidate.window!=window",
            "CGRectGetHeight(rect)<height*0.60",
            "fabs(CGRectGetMaxY(rect)-height)>75",
            "ScarletIslandP56ContainsFeedScroll(candidate,5)"):
            self.assertIn(marker,BLOCK,marker)
    def test_keeps_p56_transactional_frame_and_two_pass_zero_risk_verification(self):
        for marker in (
            "revised.origin.y=desiredY;",
            "revised.size.height-=delta;",
            "fabs(CGRectGetMaxY(revised)-CGRectGetMaxY(originalBody))<1",
            "BOOL provenBody=bodyTrial",
            "unsafe==0;",
            "BOOL bodyAccepted=provenBody && reduced;",
            "guest_owner_content_reflow_reverted",
            "guest_owner_content_reflow_retained",
            "feed.frame=oldFeed;"):
            self.assertIn(marker,OWNER,marker)
    def test_does_not_modify_global_guest_window_or_scroll_content_configuration(self):
        for forbidden in (
            "window.frame=","root.frame=","root.additionalSafeAreaInsets=",
            "scroll.contentInset=","scroll.contentOffset=",
            "method_exchangeImplementations("):
            self.assertNotIn(forbidden,BLOCK)
        self.assertIn("p59_unique_residual_unsafe_owner",OWNER)
    def test_p59_package_identity_ci_release(self):
        for marker in (
            "fix/scarlet-v48-r6p59-unsafe-feed-owner-20261114",
            "SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.59)",
            'version="3.8.59" if "r6p59"',
            "scarlet-v48-r6p59-unsafe-feed-owner-unsigned-20261114",
            "Scarlet-Crystal-V48-R6P59-UNSAFE-FEED-OWNER-UNSIGNED.ipa"):
            self.assertIn(marker,W,marker)

if __name__=="__main__":
    unittest.main()
