"""R6P35: resolve P34's truncated ancestry rather than retrying insets.

Real signed P34 SourceCommit 13762caa467 session 563f2fcd PID2894
650/2600ms: 8 unsafe UI controls, 7 unsafe images; root safeTop62.
5 controls in short owner are y60, while 3 severe buttons at y3/13
have zero measured constraints but P34's 8-hop scan is capped on
all 3 (constraint_inspected=2, constraint_scan_capped=1).
Therefore absence of observed constraints is NOT proof of manual layout.
P35 traces selected severe controls up to controller root in a
bounded read-only pass; previously failed L063/L071/L072/L074/L076
mutators stay quarantined.
"""
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
G = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
R = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()


class AncestorLayoutOwnerProbe(unittest.TestCase):
    def test_only_two_severely_unsafe_nodes_traced_after_stabilization(self):
        section = G.split("// R6P35: P34 signed iPhone", 1)[1].split(
            "static void ScarletIslandContentProbe", 1)[0]
        for token in (
            "sample != 2600", "selected >= 2", "rows.count >= 48",
            "hops < 24", "CGRectGetMinY(shown) >= safeTop - 20",
            "ScarletIslandVisibleFrameInWindow",
            "ScarletIslandAnonymousSlot(node)",
            "guest_ancestor_layout_probe",
            "ancestor_guide_y", "ancestor_vertical_constraints",
            "ancestor_translates", "ancestor_autoresize_mask",
            "ancestor_is_controller_root", "ancestor_controller_safe_top",
            "ancestor_is_owner", "ancestor_is_root", "root_reached_nodes",
            "owner_reached_nodes", "ancestor_rows_capped",
        ):
            self.assertIn(token, section)
        self.assertEqual(
            G.count("ScarletIslandProbeUnsafeAncestorChain(\n        window, rootView, expectedTop, sample, ownerGroups);"), 1)

    def test_no_visual_mutations_or_user_specific_data(self):
        section = G.split("// R6P35: P34 signed iPhone", 1)[1].split(
            "static void ScarletIslandContentProbe", 1)[0]
        forbidden = (
            "contentInset =", "contentOffset =", "additionalSafeAreaInsets =",
            "window.frame =", "root.frame =", "cursor.frame =",
            "center =", "transform =", "constraint.constant =",
            "constraint.active =", "method_exchangeImplementations",
            "NSStringFromClass", "accessibilityLabel",
            "accessibilityIdentifier", "guest_ref", "bundleIdentifier",
            "island.hidden =",
        )
        for token in forbidden:
            self.assertNotIn(token, section)

    def test_real_p34_truncated_chain_is_not_falsely_declared_manual(self):
        # P34 inspected only two constraints at up to eight ancestors,
        # and capped precisely the three severe controls. P35 extends
        # chain observation without modifying the old P34 logic.
        p34 = G.split("static void ScarletIslandProbeConstraints(", 1)[1].split(
            "// R6P35: P34 signed iPhone", 1)[0]
        self.assertIn("levels++ < 8", p34)
        self.assertIn("if(cursor && cursor != owner) capped=YES", p34)
        p35 = G.split("// R6P35: P34 signed iPhone", 1)[1].split(
            "static void ScarletIslandContentProbe", 1)[0]
        self.assertIn("hops < 24", p35)
        self.assertIn("if(!rootReached) capped = YES", p35)
        self.assertIn("cursor == root", p35)
        severe_y = [60] * 5 + [13, 3, 3]
        self.assertEqual(sum(y < 62 - 20 for y in severe_y), 3)

    def test_host_keeps_bound_48_rows_and_recorder_whitelists_every_field(self):
        self.assertIn('result == "guest_ancestor_layout_probe"', H)
        self.assertIn("nodes.prefix(48)", H)
        self.assertIn('ScarletIslandPublish(@{', G)
        for key in (
            "node_slot", "scroll_slot", "ancestor_slot", "ancestor_depth",
            "ancestor_window_y", "ancestor_parent_window_y",
            "ancestor_local_y", "ancestor_guide_y", "ancestor_safe_top",
            "ancestor_bounds_y", "ancestor_height",
            "ancestor_vertical_constraints", "ancestor_autoresize_mask",
            "ancestor_translates", "ancestor_is_controller_root",
            "ancestor_controller_safe_top", "ancestor_is_scroll",
            "ancestor_is_control", "ancestor_clips", "ancestor_has_transform",
            "ancestor_is_owner", "ancestor_is_root",
            "selected_nodes", "owner_reached_nodes", "root_reached_nodes",
            "ancestor_rows_capped"
        ):
            self.assertIn('@"' + key + '"', G)
            self.assertIn('"' + key + '"', H)
            self.assertIn('"' + key + '"', R)

    def test_old_known_bad_uikit_inset_mutators_still_quarantined(self):
        self.assertNotIn(
            "ScarletIslandScheduleVisibleLocalOwnerRepair(window, root, target);", G)
        self.assertNotIn(
            "ScarletIslandScheduleNonverticalAlwaysInset(window, root, target);", G)
        self.assertNotIn(
            "ScarletIslandScheduleResidualAutomaticInset(window, root, target);", G)
        self.assertIn('guest_always_policy_quarantined', G)
        self.assertIn('guest_local_owner_quarantined', G)


if __name__ == "__main__":
    unittest.main()
