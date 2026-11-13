"""P52 ancestry regression; static contracts are not signed-device touch proof."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
G = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
B = G.split("static void ScarletIslandTryP44LocalHeaderTransform(", 2)[-1].split(
    "static void ScarletIslandTryDeepHeaderSafeGuideAnchor(", 1)[0]

class CompositeHeader(unittest.TestCase):
    def test_plain_header_requires_direct_controller_parent_and_unique_controls(self):
        for token in ("parentVC.view!=p", "BOOL composite=responder==p",
                      "if(!childOwned && !composite) continue", "header!=candidate",
                      "node==first || node==second", "conflict || severe<2"):
            self.assertIn(token, B)
        for native in ("UIScrollView", "UIControl", "UINavigationBar", "UITabBar", "UIWindow"):
            self.assertIn("![cursor isKindOfClass:"+native+".class]", B)
        self.assertIn("((UIViewController *)responder).parentViewController==parentVC", B)
    def test_same_bounded_pilot_and_revert_without_scene_crop_or_theme_override(self):
        for token in ("(sample!=650 && sample!=2600)", "scarletIslandP44HeaderTransformTrialKey",
                      "ScarletIslandDeepHeaderOwnerReady(", "unsafe+2<=beforeControls",
                      "images<=beforeImages+1", "(int64_t)220*NSEC_PER_MSEC",
                      "(int64_t)1050*NSEC_PER_MSEC", "head.transform=original"):
            self.assertIn(token, B)
        for forbidden in ("header.frame=", "root.frame=", "window.frame=", "contentInset=",
                          "contentOffset=", "NSLayoutConstraint", "setFrame:"):
            self.assertNotIn(forbidden, B)
        self.assertNotIn(".preferredColorScheme(", H)
    def test_staged_receipt_distinguishes_new_ownership_without_private_names(self):
        self.assertIn('@"composite_header_under_controller"', B)
        self.assertIn('@"isolated_interactive_header"', B)
        self.assertNotIn("NSStringFromClass", B)
        self.assertNotIn("accessibilityLabel", B)
if __name__ == "__main__": unittest.main()
