"""R6P31 native-safearea contract and falsifiable long-readback regression.

Signed P30 SourceCommit 04d2930ee603 session aa3eede3 PID1392:
the P28 manual inset was quarantined, P29 fullscreen residual owner
was matched with 3 unsafe controls but UIKit AUTOMATIC adjusted inset
remained 0, and the experiment reverted. Existing 650ms and 2600ms
visible unsafe count stayed 8 / images 6. Apple's ALWAYS enum differs
from AUTOMATIC on non-vertical/short content.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
HOST = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()


class NonverticalAlwaysSafeArea(unittest.TestCase):
    def test_same_strict_unique_owner_gate_but_distinct_uikit_policy(self):
        section = SRC.split("static void ScarletIslandTryResidualAutomaticInset(", 1)[1].split(
            "static void ScarletIslandScheduleResidualAutomaticInset(", 1)[0]
        for token in (
            "fabs(CGRectGetMinY(rect)) <= 3",
            "candidate.scrollEnabled",
            "contentRatio >= 0.85 && contentRatio <= 1.12",
            "fabs(localSafe - expectedTop) <= 2",
            "UIScrollViewContentInsetAdjustmentNever",
            "if(selected)",
            "UIScrollViewContentInsetAdjustmentAlways",
            "UIScrollViewContentInsetAdjustmentAutomatic",
            "always ?",
            "if(always && isfinite(selected.adjustedContentInset.top)",
            "anchored.y = -selected.adjustedContentInset.top",
            "selected.contentOffset = anchored",
            "selectedControls",
        ):
            self.assertIn(token, section)
        self.assertIn("ScarletIslandTryResidualAutomaticInset(", SRC)
        self.assertIn("weakWindow, weakRoot, expectedTop, YES", SRC)
        self.assertIn("weakWindow, weakRoot, expectedTop, NO", SRC)

    def test_two_phase_success_retained_only_after_late_measured_pass(self):
        section = SRC.split("if(always) {\n            // A one-frame success",1)[1].split(
            "objc_setAssociatedObject(owner, &scarletIslandResidualAutoAppliedKey",1)[0]
        for token in (
            "guest_always_trial_staged",
            "native_inset_tentative",
            "(int64_t)1100 * NSEC_PER_MSEC",
            "lateControls < selectedControls",
            "lateInset >= expectedTop - 3",
            "lateInset <= expectedTop + 12",
            "fabs(stableOwner.contentOffset.y + lateInset) <= 3",
            "guest_always_trial_reverted",
            "late_geometry_not_persistent",
            "guest_always_trial_retained",
            "late_native_inset_confirmed",
            "&scarletIslandAlwaysAppliedKey"
        ):
            self.assertIn(token, section)
        self.assertLess(section.index("guest_always_trial_staged"),
                        section.index("guest_always_trial_retained"))

    def test_no_manual_insets_root_window_transforms_or_p28_reactivation(self):
        p31 = SRC.split("// R6P31: UIKit ALWAYS", 1)[1].split(
            "void initScarletGuestIslandContentGuard",1)[0]
        for forbidden in ("root.additionalSafeAreaInsets =", "window.frame =",
                          "UIScrollViewContentInsetAdjustmentAutomatic;",
                          "method_exchangeImplementations", "contentInset.top +=",
                          "vc.scaleRatio =", "setStatusBarHidden:"):
            self.assertNotIn(forbidden, p31)
        self.assertNotIn("ScarletIslandScheduleVisibleLocalOwnerRepair(window, root, target);", SRC)
        self.assertIn('ScarletIslandReceipt(@"guest_local_owner_quarantined"', SRC)
        self.assertNotIn("ScarletIslandScheduleResidualAutomaticInset(window, root, target);", SRC)
        self.assertEqual(SRC.count("ScarletIslandScheduleNonverticalAlwaysInset(window, root, target);"),0)

    def test_final_device_jsonl_has_unredacted_quarantine_and_stage_types(self):
        for token in (
            '"guest_local_owner_quarantined"',
            '"guest_always_trial_staged"',
            '"guest_always_trial_reverted"',
            '"guest_always_trial_retained"',
            '"guest_always_inset_receipt"',
            '"owner_auto_before_pt"',
            '"owner_auto_after_pt"',
            '"visible_unsafe_controls"',
            '"late_geometry_not_persistent"',
            '"late_native_inset_confirmed"',
        ):
            self.assertIn(token, HOST)
        self.assertIn("ScarletIslandScheduleNonverticalAlwaysInset(", SRC)
        self.assertIn("(int64_t)1850 * NSEC_PER_MSEC", SRC)


if __name__ == "__main__":
    unittest.main()
