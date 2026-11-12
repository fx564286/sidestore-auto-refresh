"""R6P22: causal correction is scroll content, not the already-safe root.

R6P21 on-device PID 6059: root/guide safe top 62pt, but eight
interactive control frames begin at y=3pt; seven image nodes y=13pt
and three scrollers have no adjusted top inset. PID 6050 showed none.
The correction must be one-shot, opt-in and limited to one provably
unsafe vertical scroller; otherwise leave the app's layout untouched.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUARD = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
HOST = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()

class GuardedGuestScrollContentInset(unittest.TestCase):
    def test_root_receipt_still_unchanged_and_correction_is_separate(self):
        self.assertIn("if(before >= target - 2)", GUARD)
        self.assertIn("guest_root_already_safe", GUARD)
        self.assertIn("ScarletIslandScheduleContentProbe(window, root, target);", GUARD)
        self.assertNotIn("ScarletIslandScheduleScrollContentRepair(window, root, target);", GUARD)
        self.assertIn("root.additionalSafeAreaInsets = extra;", GUARD)
        self.assertEqual(GUARD.count("ScarletIslandScheduleScrollContentRepair(window, root, target);"),0)

    def test_no_global_app_window_or_status_bar_mutation(self):
        fix = GUARD.split("// R6P22: unlike the L050 root correction",1)[1].split("// R6P28: unique visible control owner",1)[0]
        for forbidden in ("window.frame =", "root.additionalSafeAreaInsets =",
                          "window.rootViewController =", "setStatusBarHidden",
                          "method_exchangeImplementations", "NSStringFromClass",
                          "accessibilityLabel", "screenshot", "bundleIdentifier",
                          "contentInsetAdjustmentBehavior ="):
            self.assertNotIn(forbidden, fix)
        self.assertIn("window.rootViewController != root",fix)
        self.assertIn("UIInterfaceOrientationIsPortrait",fix)
        self.assertIn("rootView.safeAreaInsets.top < expectedTop - 2",fix)

    def test_single_full_width_vertical_unsafe_scroll_only(self):
        fix = GUARD.split("// R6P22: unlike the L050 root correction",1)[1].split("// R6P28: unique visible control owner",1)[0]
        for required in ("candidates.count != 1", "CGFloat deficit = ceil(",
                         "CGRectGetWidth(window.bounds) * 0.7",
                         "CGRectGetHeight(window.bounds) * 0.4",
                         "scroll.contentSize.height > scroll.bounds.size.height + 12",
                         "scroll.adjustedContentInset.top < 2",
                         "ScarletIslandHasUnsafeScrollControl(",
                         "UIAccessibilityTraitButton", "top < safeY - 2",
                         "BOOL nested = NO", "scroll.dragging",
                         "scroll.tracking", "scroll.decelerating",
                         "scroll.contentOffset.y >= -2"):
            self.assertIn(required,fix)

    def test_content_inset_owned_once_and_snapshot_precedes_it(self):
        fix=GUARD.split("// R6P22: unlike the L050 root correction",1)[1].split("// R6P28: unique visible control owner",1)[0]
        self.assertIn("objc_getAssociatedObject(",fix)
        self.assertIn("&scarletIslandScrollInsetKey",fix)
        self.assertIn("objc_setAssociatedObject(scroll, &scarletIslandScrollInsetKey",fix)
        self.assertIn("inset.top += deficit;",fix)
        self.assertIn("scroll.contentInset = inset;",fix)
        self.assertIn("offset.y = -scroll.adjustedContentInset.top;",fix)
        self.assertIn("scroll.contentOffset = offset;",fix)
        self.assertIn('@"guest_scroll_content_inset_applied"',fix)
        self.assertIn('@"guest_scroll_no_unique_unsafe_target"',fix)
        self.assertIn('for(NSNumber *delay in @[@650, @2600])',GUARD)
        self.assertIn("(int64_t)900 * NSEC_PER_MSEC",fix)
        self.assertIn("ScarletIslandReceipt(@",fix)

    def test_existing_guest_mode_isolation_stays_enabled(self):
        self.assertIn("if(!NSUserDefaults.isLiveProcess ||",GUARD)
        self.assertIn('boolForKey:@"Scarlet.ResidentSDKContract.V1"',GUARD)
        self.assertIn("ScarletIslandScheduleContentProbe",GUARD)
        self.assertIn("fullscreen_scene_remote_content_attached",HOST)

if __name__ == "__main__":
    unittest.main()
