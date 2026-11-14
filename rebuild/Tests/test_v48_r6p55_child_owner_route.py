"""P55: reachable native owner repair for signed child-controller header."""
import unittest
from pathlib import Path
G=(Path(__file__).resolve().parents[1]/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
TRIAL=G.split("static void ScarletIslandTryP44LocalHeaderTransform(",2)[-1].split("static void ScarletIslandTryDeepHeaderSafeGuideAnchor(",1)[0]
OWNER=G.split("// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN",1)[1].split("// R6P54_OWNER_LAYOUT_CONTRACT_END",1)[0]
class P55ChildOwnership(unittest.TestCase):
    def test_signed_p54_child_header_now_reaches_parent_layout_hook(self):
        # Session 990090a7 PID1841: match=1, parent layout origin=3,
        # header height=50, header Y0, guide Y62, unsafe9 -> 6 -> invalid.
        for marker in (
            "headerKind==1", "measuredChild.parentViewController==measuredParent",
            "measuredParent.view==parent", "measuredChild.view==header",
            "fabs(CGRectGetHeight(header.bounds)-50)<4",
            "method_getImplementation(parentLayout)!=method_getImplementation(systemLayout)",
            "if(headerKind==2 || measuredChildParent)",
        ):
            self.assertIn(marker, TRIAL, marker)
        self.assertIn("if(measuredChildParent) {",TRIAL)
        self.assertLess(TRIAL.index("if(measuredChildParent) {"),
                        TRIAL.index("header.transform=CGAffineTransformTranslate"))
    def test_native_owner_accepts_both_exactly_scoped_responder_topologies(self):
        for marker in (
            "BOOL plainComposite=headerResponder==parent",
            "BOOL childOwned=[headerResponder isKindOfClass:UIViewController.class]",
            "((UIViewController *)headerResponder).view==header",
            "((UIViewController *)headerResponder).parentViewController==owner",
            "(!plainComposite && !childOwned)",
            "object_setClass(owner,scoped)",
            "ScarletIslandP54AfterNativeOwnerLayout(receiver)",
            "unsafe+2<=beforeControls", "object_setClass(vc,original)",
        ):self.assertIn(marker,OWNER,marker)
        for forbidden in ("window.frame=", "root.frame=", "header.transform=",
                "scroll.contentInset=", "method_exchangeImplementations("):
            self.assertNotIn(forbidden,OWNER)
    def test_guard_preserves_other_guest_shapes_and_full_frame(self):
        self.assertIn("if(headerKind==2 || measuredChildParent)",TRIAL)
        self.assertIn("if(measuredChildParent) {",TRIAL)
        self.assertIn("fabs(CGRectGetHeight(header.bounds)-50)<4",TRIAL)
        self.assertNotIn("window.bounds=CGRect",TRIAL)
if __name__=="__main__":unittest.main()
