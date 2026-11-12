"""P39 explicit header Auto Layout contract distinct from P37 one-off frame."""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SRC=(ROOT/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
HOST=(ROOT/"HostApp/ScarletFullscreenSceneStack.swift").read_text()
WORKFLOW=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
BODY=SRC.split("// R6P39_CONSTRAINT_BRIDGE_BEGIN",1)[1].split(
    "// R6P39_CONSTRAINT_BRIDGE_END",1)[0]
class MeasuredChildLayout(unittest.TestCase):
    def test_parent_observer_only_calls_new_constraint_fix_after_owner(self):
        probe=SRC.split("static void ScarletIslandContentProbe(",1)[1].split(
            "// R6P37 distinct measured",1)[0]
        self.assertIn("ScarletIslandObserveDeepHeaderLayoutOwner(",probe)
        self.assertNotIn("ScarletIslandTryDeepHeaderSafeGuideAnchor(",probe)
        p38=SRC.split("// R6P38_LAYOUT_OWNER_BEGIN",1)[1].split(
            "// R6P38_LAYOUT_OWNER_END",1)[0]
        self.assertNotIn("    ScarletIslandTryMeasuredHeaderConstraintBridge(",p38)
        self.assertIn("    if(!found) { ScarletIslandPublish(fields); return; }",p38)
    def test_only_unique_measured_header_is_anchored(self):
        for token in ("sample!=2600","hasOwnHeight","header.superview!=parent",
                      "child.parentViewController!=owner",
                      "header.autoresizingMask!=UIViewAutoresizingNone",
                      "parent.safeAreaLayoutGuide.topAnchor",
                      "header.leadingAnchor", "header.widthAnchor",
                      "NSAutoresizingMaskLayoutConstraint",
                      "header.translatesAutoresizingMaskIntoConstraints=NO",
                      "[NSLayoutConstraint activateConstraints:owned]"):
            self.assertIn(token,BODY,token)
        for forbidden in ("window.frame=", "root.frame=", "contentInset=",
                          "contentOffset=", "contentInsetAdjustmentBehavior=",
                          "transform=", "method_setImplementation",
                          "method_exchangeImplementations",
                          "layoutIfNeeded", "setNeedsLayout"):
            self.assertNotIn(forbidden,BODY,forbidden)
    def test_reversible_treatment_relay_and_bounded_proof(self):
        for token in ("240*NSEC_PER_MSEC", "1200*NSEC_PER_MSEC",
                      "deactivateConstraints:owned", "beforeControls",
                      "controls+2<=beforeControls","lateControls+2<=beforeControls",
                      "CGRectGetMinY(a)>=safeTop-2","CGRectGetMinY(two)>=safeTop-2",
                      "guest_header_constraint_bridge_reverted",
                      "guest_header_constraint_bridge_retained",
                      "guest_header_constraint_bridge_staged"):
            self.assertIn(token,BODY,token)
        for key in ("guest_header_constraint_bridge_receipt",
                    "guest_header_constraint_bridge_staged",
                    "guest_header_constraint_bridge_reverted",
                    "guest_header_constraint_bridge_retained",
                    "parent_safe_guide_constraint", "late_native_anchor_confirmed"):
            self.assertIn(key,HOST,key)
        for secret in ("bundleIdentifier","accessibilityLabel","localizedDescription",
                       "NSStringFromClass","dli_fname", "image_path"):
            self.assertNotIn(secret,BODY,secret)
    def test_ci_has_distinct_branch_artifact_release(self):
        self.assertIn("fix/scarlet-v48-r6p39-parent-safe-guide-constraint-20261113",WORKFLOW)
        self.assertIn("Scarlet-Crystal-V48-R6P39-PARENT-CONSTRAINT-UNSIGNED.ipa",WORKFLOW)
        self.assertIn("scarlet-v48-r6p39-parent-constraint-unsigned-20261113",WORKFLOW)
if __name__=="__main__":unittest.main()
