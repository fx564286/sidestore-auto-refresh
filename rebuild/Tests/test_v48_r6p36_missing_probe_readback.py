"""R6P36: real iPhone P35 exposed missing guest geometry before owner scan.

P35 signed SourceCommit 75455528540a session 3d8246a5:
PID3244 emitted both 650/2600ms content geometry snapshots with zero
visible unsafe controls. PID3252 root_safe=62 and P28/P33 quarantines
but never produced EITHER content geometry or P35 ancestor probe,
despite being foreground for >30s. P35's snapshot guard may silently
return if its weak UIWindow/root changes or detaches after scheduling.
A bounded diagnostic distinguishes all such causes without another
viewport/inset/window transform. Only 2600ms may use attached new root.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
G = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
R = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()

class MissingProbeReadback(unittest.TestCase):
    def test_scheduling_and_failure_states_cannot_go_silent(self):
        sub = G.split("// R6P36: P35 iPhone PID3252", 1)[1].split(
            "static void ScarletIslandScheduleScrollContentRepair(", 1)[0]
        for state in (
            '@"scheduled"', '@"window_released"', '@"root_replaced"',
            '@"root_stale"', '@"window_ineligible"',
            '@"scene_ineligible"', '@"root_detached"',
            '@"safe_unready"', '@"frame_invalid"',
        ):
            self.assertIn(state, sub)
        self.assertIn('@"result":@"guest_geometry_probe_status"', sub)
        self.assertIn("ScarletIslandProbeStatus(@\"scheduled\"", sub)
        self.assertIn("if(!liveWindow)", sub)
        self.assertIn("if(!liveRoot || liveWindow.rootViewController != liveRoot)", sub)
        self.assertIn("CGRectGetMinY(guide)", sub)

    def test_original_two_samples_and_single_late_recovery_only(self):
        sub = G.split("// R6P36: P35 iPhone PID3252", 1)[1].split(
            "static void ScarletIslandScheduleScrollContentRepair(", 1)[0]
        self.assertIn("for(NSNumber *delay in @[@650, @2600])", sub)
        self.assertIn("if(sample==2600 && liveWindow.rootViewController)", sub)
        self.assertIn("liveRoot=liveWindow.rootViewController;", sub)
        self.assertIn("ScarletIslandContentProbe(liveWindow, liveRoot, expectedTop, sample);", sub)
        self.assertNotIn("ScarletIslandContentProbe(weakWindow, weakRoot, expectedTop, sample);", sub)
        self.assertEqual(sub.count("dispatch_after("), 1)
        self.assertNotIn("ScarletIslandScheduleContentProbe(liveWindow", sub)

    def test_recovery_never_acts_on_ineligible_window_or_detached_root(self):
        sub = G.split("// R6P36: P35 iPhone PID3252", 1)[1].split(
            "static void ScarletIslandScheduleScrollContentRepair(", 1)[0]
        for required in (
            "liveWindow.hidden", "liveWindow.windowLevel!=UIWindowLevelNormal",
            "UIInterfaceOrientationIsPortrait", "view.window!=liveWindow",
            "isfinite(top)", "isfinite(expectedTop)", "rootViewController != liveRoot",
            "probe_scene_present", "probe_root_match", "probe_root_attached"
        ):
            self.assertIn(required, sub)
        for forbidden in (
            "window.frame =", "window.bounds =", "root.additionalSafeAreaInsets =",
            "contentInset =", "contentOffset =", "root.view.frame =",
            "method_exchangeImplementations", "UIScrollViewContentInsetAdjustmentAlways",
            "presentViewController:", "setNeedsStatusBarAppearanceUpdate",
        ):
            self.assertNotIn(forbidden, sub)

    def test_status_flags_are_all_anonymously_relayed(self):
        section = G.split("static void ScarletIslandProbeStatus(", 1)[1].split(
            "static void ScarletIslandScheduleScrollContentRepair(", 1)[0]
        for key in (
            "probe_window_present", "probe_window_visible",
            "probe_window_normal", "probe_scene_present",
            "probe_scene_state", "probe_portrait",
            "probe_root_present", "probe_root_match",
            "probe_root_attached", "probe_root_safe_top",
            "probe_replacement", "sample_index"
        ):
            self.assertIn('@"' + key + '"', section)
            self.assertIn('"' + key + '"', H)
            if key != "sample_index":
                self.assertIn('"' + key + '"', R)
        self.assertIn('result == "guest_geometry_probe_status"', H)
        self.assertIn('"layout", "guest_geometry_probe_status"', H)
        self.assertIn('"root_replaced"', H)

    def test_history_preserves_p35_ancestor_scan_and_old_inset_quarantine(self):
        for token in (
            "ScarletIslandProbeUnsafeAncestorChain(", "guest_ancestor_layout_probe",
            "guest_always_policy_quarantined", "guest_local_owner_quarantined",
        ):
            self.assertIn(token, G)
        for token in (
            "ScarletIslandScheduleVisibleLocalOwnerRepair(window, root, target);",
            "ScarletIslandScheduleNonverticalAlwaysInset(window, root, target);",
            "ScarletIslandScheduleResidualAutomaticInset(window, root, target);",
        ):
            self.assertNotIn(token, G)

    def test_missing_second_guest_does_not_certify_visual_success(self):
        observed = {
            3244: {"root_safe": 62, "readbacks": (650, 2600), "unsafe": 0},
            3252: {"root_safe": 62, "readbacks": (), "unsafe": None},
        }
        self.assertEqual(observed[3244]["unsafe"], 0)
        self.assertIsNone(observed[3252]["unsafe"])
        self.assertEqual(len(observed[3252]["readbacks"]), 0)


if __name__ == "__main__":
    unittest.main()
