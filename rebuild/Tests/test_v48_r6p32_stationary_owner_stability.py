"""R6P32 iPhone P30 c1e6cef0: stationary fullscreen residual owner.

R6P30 SourceCommit 04d2930ee603 PID1604:
1850ms: owner_groups1 candidate_with_controls1/frame1/safe1/content1,
inset0/state0 => no_matching_fullscreen_owner. At 2600ms, window
y0, height100%, width103%, safeTop62, adjustedInset0, behaviorNEVER,
content100%, scrollEnabled0, offset0; 4 unsafe controls/4 images.
R6P31's ALWAYS path still required scrollEnabled=YES. R6P32 changes
candidate readiness/eligibility, not the UIKit inset/visual strategy.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
R = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()


class StationaryNativeOwnerStability(unittest.TestCase):
    def test_legacy_automatic_keeps_scroll_enabled_requirement(self):
        section = G.split("static void ScarletIslandTryResidualAutomaticInset(",1)[1].split(
            "static void ScarletIslandScheduleResidualAutomaticInset(",1)[0]
        for required in (
            "BOOL always, BOOL finalPass", "(always || candidate.scrollEnabled)",
            "UIScrollViewContentInsetAdjustmentNever",
            "fabs(adjusted) <= 1 && fabs(explicitInset) <= 1",
            "fabs(localSafe - expectedTop) <= 2",
            "contentRatio >= 0.85 && contentRatio <= 1.12",
            "CGRectGetHeight(rect) >= winH * 0.85",
            "if(selected)", "multiple_matching_owners",
            "!candidate.dragging && !candidate.tracking",
        ):
            self.assertIn(required, section)
        self.assertIn("weakWindow, weakRoot, expectedTop, NO, YES", G)
        self.assertIn("weakWindow, weakRoot, expectedTop, YES, NO", G)
        self.assertNotIn("candidate.scrollEnabled = YES", section)
        self.assertNotIn("candidate.scrollEnabled = NO", section)

    def test_defer_on_strict_gate_mismatch_only_once(self):
        section = G.split("if(!selected) {\n        ScarletIslandPublish",1)[1].split(
            "// No frame, transform,",1)[0]
        for required in (
            "guest_residual_auto_classifier", "candidate_disabled_scroll",
            "owner_gate_pass", "if(always && !finalPass)",
            "guest_always_owner_retry_scheduled", "owner_metrics_not_stable",
            "(int64_t)900 * NSEC_PER_MSEC",
            "expectedTop, YES, YES",
            "guest_always_owner_retry_exhausted",
            "strict_owner_unavailable_after_retry",
        ):
            self.assertIn(required, section)
        self.assertEqual(section.count("ScarletIslandTryResidualAutomaticInset("),1)
        self.assertNotIn("root.additionalSafeAreaInsets =",section)
        self.assertNotIn("contentInset =", section)
        self.assertNotIn("setNeedsStatusBarAppearanceUpdate",section)

    def test_only_existing_native_always_trial_modifies_selected_owner(self):
        section = G.split("static void ScarletIslandTryResidualAutomaticInset(",1)[1].split(
            "static void ScarletIslandScheduleResidualAutomaticInset(",1)[0]
        self.assertIn("UIScrollViewContentInsetAdjustmentAlways",section)
        self.assertIn("anchored.y = -selected.adjustedContentInset.top",section)
        self.assertIn("lateControls < selectedControls",section)
        self.assertIn("late_geometry_not_persistent",section)
        self.assertIn("guest_always_trial_retained",section)
        self.assertNotIn("window.frame =",section)
        self.assertNotIn("root.additionalSafeAreaInsets =",section)
        self.assertNotIn("candidate.contentInset =",section)
        self.assertNotIn("candidate.frame =",section)
        self.assertNotIn("window.transform =",section)
        self.assertNotIn("vc.scaleRatio =",section)

    def test_anonymous_device_receipts_for_two_passes(self):
        for name in (
            '"candidate_disabled_scroll"', '"owner_gate_pass"',
            '"guest_always_owner_retry_scheduled"',
            '"guest_always_owner_retry_exhausted"',
            '"strict_owner_unavailable_after_retry"',
            '"owner_metrics_not_stable"',
            '"guest_always_inset_receipt"',
        ):
            self.assertIn(name,H)
        for name in ('"candidate_disabled_scroll"', '"owner_gate_pass"'):
            self.assertIn(name,R)
        self.assertIn('guest_local_owner_quarantined', H)


if __name__ == "__main__":
    unittest.main()
