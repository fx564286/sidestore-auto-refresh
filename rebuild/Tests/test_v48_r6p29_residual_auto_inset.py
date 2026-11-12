"""R6P29: iPhone-backed residual scroll owner, bounded UIKit auto-inset trial.

P28 device f00c0d4 PID698, before 8 visible unsafe controls and 6
unsafe images. The local Y50 header was adjusted 3->12pt, yet 3 visible
controls + 2 images remained in a different full-viewport owner at Y0.
No app names, IDs, content, display transforms, or credentials.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
R = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()


def residual_candidate(root_safe, frame_y, width_pct, height_pct, local_safe,
                       content_height_pct, auto_mode_never, actual_controls):
    return (
        abs(frame_y) <= 3
        and 97 <= width_pct <= 110
        and 85 <= height_pct <= 112
        and abs(local_safe - root_safe) <= 2
        and 85 <= content_height_pct <= 112
        and auto_mode_never
        and actual_controls >= 2
    )


class ResidualUIKitAutomaticInsets(unittest.TestCase):
    def test_device_verified_second_owner_is_distinct_from_p28_header(self):
        self.assertTrue(residual_candidate(62, 0, 103, 100, 62, 100, True, 3))
        self.assertFalse(residual_candidate(62, 50, 100, 13, 12, 88, True, 5))
        self.assertFalse(residual_candidate(62, 0, 103, 100, 62, 100, False, 3))
        self.assertFalse(residual_candidate(62, 0, 103, 100, 62, 100, True, 1))

    def test_one_owner_only_and_always_bounded_reversible_trial(self):
        section = G.split("// R6P29: R6P28 actual signed iPhone", 1)[1].split(
            "void initScarletGuestIslandContentGuard", 1)[0]
        for needle in (
            "metrics.visibleUnsafeControls < 2",
            "if(selected)",
            "multiple_matching_owners",
            "no_matching_fullscreen_owner",
            "CGRectGetHeight(rect) >= winH * 0.85",
            "fabs(localSafe - expectedTop) <= 2",
            "UIScrollViewContentInsetAdjustmentNever",
            "UIScrollViewContentInsetAdjustmentAutomatic",
            "remaining < selectedControls",
            "after >= expectedTop - 3",
            "guest_residual_auto_reverted",
            "no_measured_overlap_reduction",
            "guest_residual_auto_retained",
            "automatic_inset_proved",
            "owner.contentOffset = originalOffset",
            "(int64_t)1850 * NSEC_PER_MSEC",
            "(int64_t)180 * NSEC_PER_MSEC",
        ):
            self.assertIn(needle, section)
        for unsafe in (
            "window.frame =", "root.additionalSafeAreaInsets =",
            "scroll.contentInset =", "setStatusBarHidden:",
            "method_exchangeImplementations", "vc.scaleRatio =",
            "accessibilityLabel", "UIImagePNGRepresentation"
        ):
            self.assertNotIn(unsafe, section)

    def test_root_and_p28_path_preserved_and_receipt_relayed(self):
        self.assertIn("ScarletIslandScheduleScrollContentRepair(window, root, target);", G)
        # R6P30: the P28 mutator is preserved for audit, but not scheduled.
        self.assertNotIn("ScarletIslandScheduleVisibleLocalOwnerRepair(window, root, target);", G)
        self.assertIn("guest_local_owner_quarantined", G)
        self.assertIn("ScarletIslandScheduleNonverticalAlwaysInset(window, root, target);", G)
        self.assertEqual(G.count("ScarletIslandScheduleNonverticalAlwaysInset(window, root, target);"), 1)
        self.assertIn('for(NSNumber *delay in @[@650, @2600])', G)
        for needle in (
            "guest_residual_auto_inset_receipt", "guest_residual_auto_retained",
            "guest_residual_auto_reverted", "guest_residual_auto_skipped",
            "owner_auto_before_pt", "owner_auto_after_pt",
            "no_measured_overlap_reduction", "automatic_inset_proved"
        ):
            self.assertIn(needle, H)
        for needle in ('"owner_auto_before_pt"', '"owner_auto_after_pt"'):
            self.assertIn(needle, R)


if __name__ == "__main__":
    unittest.main()
