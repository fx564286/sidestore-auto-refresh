"""R6P30: signed-device causality guard after P29 failure.

iPhone P29 cc5bafc85b66 session 92959d1f PID1059: L071 writes local
inset 3->12 then the app's later layout reports 3, shifts header y50->23,
and visible unsafe controls increase 8->9/images 6->8. L072's trial
never matched, reason no_matching_fullscreen_owner. The new action is
an explicit quarantine of L071, not another manual inset adjustment.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
G = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
R = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()


class DeviceInformedInterferenceIsolation(unittest.TestCase):
    def test_old_manual_inset_is_retained_for_audit_but_not_called(self):
        self.assertIn("static void ScarletIslandRepairVisibleLocalScrollOwner(", G)
        self.assertIn("static void ScarletIslandScheduleVisibleLocalOwnerRepair(", G)
        self.assertIn("guest_local_owner_inset_applied", G)
        self.assertNotIn("ScarletIslandScheduleVisibleLocalOwnerRepair(window, root, target);", G)
        self.assertIn("guest_local_owner_quarantined", G)
        self.assertIn("&scarletIslandP28QuarantineReceiptKey", G)
        self.assertIn("ScarletIslandReceipt(@\"guest_local_owner_quarantined\"", G)

    def test_new_strategy_remains_available_without_second_manual_inset(self):
        self.assertNotIn("ScarletIslandScheduleNonverticalAlwaysInset(window, root, target);", G)
        self.assertEqual(
            G.count("ScarletIslandScheduleNonverticalAlwaysInset(window, root, target);"), 0)
        safe = G.split("// R6P29: R6P28 actual signed iPhone", 1)[1].split(
            "void initScarletGuestIslandContentGuard", 1)[0]
        self.assertIn("UIScrollViewContentInsetAdjustmentAutomatic", safe)
        self.assertIn("guest_residual_auto_reverted", safe)
        self.assertNotIn("inset.top += deficit", safe)
        self.assertNotIn("root.additionalSafeAreaInsets =", safe)
        self.assertNotIn("window.frame =", safe)
        self.assertNotIn("method_exchangeImplementations", safe)

    def test_skip_has_a_bounded_mechanism_specific_predicate_census(self):
        section = G.split("static void ScarletIslandTryResidualAutomaticInset(", 1)[1].split(
            "static void ScarletIslandScheduleResidualAutomaticInset(", 1)[0]
        for token in (
            "guest_residual_auto_classifier", "candidate_with_controls",
            "candidate_frame_matched", "candidate_safe_matched",
            "candidate_inset_matched", "candidate_content_matched",
            "candidate_state_matched", "no_matching_fullscreen_owner",
            "owner_groups"
        ):
            self.assertIn(token, section)
        for token in (
            "guest_residual_auto_classifier", "candidate_with_controls",
            "candidate_frame_matched", "candidate_safe_matched",
            "candidate_inset_matched", "candidate_content_matched",
            "candidate_state_matched"
        ):
            self.assertIn(token, H)
        for token in (
            '"candidate_with_controls"', '"candidate_frame_matched"',
            '"candidate_safe_matched"', '"candidate_inset_matched"',
            '"candidate_content_matched"', '"candidate_state_matched"'
        ):
            self.assertIn(token, R)

    def test_only_existing_p28_call_removed(self):
        # R6P22 remains independently gated, guest root and safe area are
        # untouched, and the P29 candidate retains strict safeguards.
        self.assertNotIn("ScarletIslandScheduleScrollContentRepair(window, root, target);", G)
        self.assertIn("ScarletIslandScheduleContentProbe(window, root, target);", G)
        self.assertIn("for(NSNumber *delay in @[@650, @2600])", G)
        self.assertIn("after >= expectedTop - 3 && after <= expectedTop + 12", G)
        self.assertIn("remaining < selectedControls", G)


if __name__ == "__main__":
    unittest.main()
