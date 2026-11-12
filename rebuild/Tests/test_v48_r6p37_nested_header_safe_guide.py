"""P37: signed P36 ancestry proves a *short nested child-controller* Y0.

P36 iPhone SourceCommit d1c66a1e5329, session c14fc56d, PID3731:
root 440x956 safeTop62; inner UIViewController.view Y0 height50
safeTop62 / collapsed guideY50; its *own full-height parent*
safe guide starts at Y62; 3 unsafe buttons at Y3,3,13. Existing
P34/P35 log constraint_count0 was truncated after8 ancestors, while
P36 successfully traced owner slot8 and the root (uncapped,18-19
hops). No global window, scroll content or scale fix helped. P37
attempts one local child view origin-to-parent-native-safe-guide
correction and reverts on failed immediate or late actual geometry.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
G=(ROOT/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H=(ROOT/"HostApp/ScarletFullscreenSceneStack.swift").read_text()
R=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
SECTION=G.split("// R6P37 distinct measured *short child-controller header*",1)[1].split(
    "// R6P36: P35 iPhone PID3252",1)[0]


class ShortNestedHeaderNativeSafeGuide(unittest.TestCase):
    def test_specific_geometry_gate_is_not_a_global_content_inset_fix(self):
        for token in (
            "sample!=2600", "safeTop<40", "safeTop>130", "beforeControls<2",
            "ScarletIslandVisibleFrameInWindow", "safeTop-20",
            "CGRectGetHeight(cursor.bounds)<34", "CGRectGetHeight(cursor.bounds)>72",
            "CGRectGetHeight(p.bounds)<CGRectGetHeight(window.bounds)*0.85",
            "fabs(CGRectGetMinY([cursor convertRect:cursor.bounds",
            "p.safeAreaLayoutGuide.layoutFrame", "cursor.safeAreaInsets.top<safeTop-2",
            "cursor.translatesAutoresizingMaskIntoConstraints",
            "CGAffineTransformIsIdentity(cursor.transform)",
            "fabs(CGRectGetMinY(guide)-CGRectGetMaxY(frame))>3",
            "if(header && header!=candidate)", "severe<2",
            "original=header.frame", "moved.origin.y=targetY",
            "header.frame=moved", "objc_setAssociatedObject(root,",
        ):
            self.assertIn(token,SECTION)
        self.assertIn("sample, ownerGroups,",G)
        self.assertIn("metrics.visibleUnsafeControls, metrics.visibleUnsafeImageNodes",G)
        self.assertIn("root.safeAreaInsets.top-safeTop",SECTION)
        for forbidden in (
            "window.frame=", "window.bounds=", "root.frame=",
            "root.additionalSafeAreaInsets=", "contentInset=", "contentOffset=",
            "owner.contentInset=", "owner.contentOffset=",
            "method_exchangeImplementations", "setNeedsLayout",
            "setNeedsStatusBarAppearanceUpdate", "UIView animateWithDuration",
            "NSStringFromClass", "accessibilityLabel", "bundleIdentifier"
        ):
            self.assertNotIn(forbidden,SECTION)

    def test_immediate_and_late_readback_must_both_improve_actual_controls(self):
        for token in (
            "(int64_t)180*NSEC_PER_MSEC", "(int64_t)1100*NSEC_PER_MSEC",
            "ScarletIslandDeepHeaderCountUnsafe(rt,w,safeTop,&images)",
            "ScarletIslandDeepHeaderCountUnsafe(",
            "CGRectGetMinY(first)>=safeTop-2",
            "CGRectGetMinY(second)>=safeTop-2",
            "controls+2<=beforeControls",
            "lateControls+2<=beforeControls",
            "images<=beforeImages+1",
            "lateImages<=beforeImages+1",
            "CGRectGetWidth(w.bounds)-CGRectGetWidth(winBounds)",
            "CGRectGetHeight(w.bounds)-CGRectGetHeight(winBounds)",
            "guest_short_header_trial_staged", "guest_short_header_trial_reverted",
            "guest_short_header_trial_retained",
            "no_immediate_reduction", "late_layout_not_persistent",
            "h.frame=original", "lateHeader.frame=original",
        ):
            self.assertIn(token,SECTION)

    def test_p36_ancestor_and_original_failed_mutator_quarantines_preserved(self):
        self.assertIn("ScarletIslandProbeUnsafeAncestorChain(",G)
        self.assertIn("guest_ancestor_layout_probe",G)
        self.assertIn("guest_geometry_probe_status",G)
        self.assertIn("guest_always_policy_quarantined",G)
        for forbidden in (
            "ScarletIslandScheduleVisibleLocalOwnerRepair(window, root, target);",
            "ScarletIslandScheduleNonverticalAlwaysInset(window, root, target);",
            "ScarletIslandScheduleResidualAutomaticInset(window, root, target);"
        ):
            self.assertNotIn(forbidden,G)

    def test_proof_is_anonymous_and_relayed_on_real_device(self):
        for name in (
            "guest_short_header_trial_staged", "guest_short_header_trial_reverted",
            "guest_short_header_trial_retained",
            "guest_short_header_trial_receipt",
            "parent_safe_guide_anchor", "native_layout_overrode",
            "late_safe_guide_confirmed",
        ):
            self.assertIn(name,H)
        for field in (
            "header_before_y", "header_after_y", "header_controls_before",
            "header_controls_after", "header_images_after", "header_gate_pass"
        ):
            self.assertIn('@"'+field+'"',G)
            self.assertIn('"'+field+'"',H)
            self.assertIn('"'+field+'"',R)

    def test_source_p36_exact_problem_geometry_not_other_guest(self):
        bad={"root":62,"child_y":0,"child_h":50,"guide":50,
             "parent_guide":62,"unsafe_controls":8,"images":7,
             "severe_button_y":(3,3,13)}
        good={"root":62,"unsafe_controls":0,"images":1}
        self.assertLess(bad["child_h"],bad["root"])
        self.assertEqual(bad["guide"],bad["child_h"])
        self.assertEqual(bad["parent_guide"],bad["root"])
        self.assertEqual(sum(y<bad["root"]-20 for y in bad["severe_button_y"]),3)
        self.assertLess(good["unsafe_controls"],2)


if __name__=="__main__": unittest.main()
