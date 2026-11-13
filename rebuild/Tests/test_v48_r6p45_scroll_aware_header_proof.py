"""P45: a scrolled native header is not automatically a failed transform.

The signed P44 receipt shows 8->5 unsafe controls, a retained transform,
then a frame-origin-only invalidation and 62pt physical FBScene crop.
These static contracts are NOT substitutes for device image/hit testing.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
GUEST=(ROOT/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
HOST=(ROOT/"HostApp/ScarletFullscreenSceneStack.swift").read_text()
DIAG=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
WORKFLOW=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()


class P45ScrollAwareHeader(unittest.TestCase):
    def test_guest_monitors_hit_targets_not_absolute_header_origin(self):
        body=GUEST.split("static void ScarletIslandP44MonitorHeader(UIWindow *window) {",1)[1]
        body=body.split("static void ScarletIslandRepeatSurfaceToneCheck(",1)[0]
        self.assertNotIn("fabs(CGRectGetMinY(frame)-top)<3",body)
        for word in ("header_affine_retained", "header_checked_controls",
                     "ScarletIslandVisibleFrameInWindow(control,window)",
                     "header_unsafe_controls", "header_invalidation_reason",
                     "guest_header_scroll_motion_safe"):
            self.assertIn(word,body)
        self.assertIn("BOOL healthy=affineRetained && checked>=2 && unsafe==0;",body)
        self.assertIn("if(healthy) {",body)
        self.assertIn("continue;",body)

    def test_safe_scroll_does_not_switch_native_guest_scene(self):
        body=GUEST.split("static void ScarletIslandP44MonitorHeader(UIWindow *window) {",1)[1]
        body=body.split("static void ScarletIslandRepeatSurfaceToneCheck(",1)[0]
        safe=body.split("if(healthy) {",1)[1].split("continue;",1)[0]
        self.assertNotIn("ScarletIslandReceipt(@\"guest_header_local_transform_invalidated",safe)
        self.assertNotIn("header.transform=CGAffineTransformIdentity",safe)
        self.assertNotIn("setFrame(",body)
        self.assertNotIn("contentInset=",body)
        self.assertNotIn("contentOffset=",body)

    def test_unsafe_and_native_transform_loss_are_fail_closed(self):
        body=GUEST.split("static void ScarletIslandP44MonitorHeader(UIWindow *window) {",1)[1]
        body=body.split("static void ScarletIslandRepeatSurfaceToneCheck(",1)[0]
        self.assertIn("if(affineRetained && checked>=2 && unsafe>0 && samples<1)",body)
        self.assertIn("CGAffineTransformEqualToTransform(header.transform,wanted)",body)
        self.assertIn('@"guest_header_local_transform_invalidated"',body)
        self.assertIn("header.transform=CGAffineTransformIdentity",body)
        self.assertIn("[headers removeObject:header]",body)

    def test_retained_p44_weak_controls_bound_to_exact_header(self):
        self.assertIn("scarletIslandP45MeasuredHeaderControlsKey",GUEST)
        self.assertIn("NSHashTable<UIView *> *proven=[NSHashTable weakObjectsHashTable];",GUEST)
        self.assertIn("if(one) [proven addObject:one];",GUEST)
        self.assertIn("if(two) [proven addObject:two];",GUEST)
        self.assertIn("[control isDescendantOfView:header]",GUEST)
        self.assertIn("head.transform=original",GUEST)

    def test_diagnostic_is_anonymized_and_result_observed_on_host(self):
        self.assertIn('"guest_header_scroll_motion_safe"',HOST)
        self.assertIn('"guest_header_local_transform_invalidated"',HOST)
        for key in ("header_current_y","header_checked_controls",
                    "header_visible_controls","header_unsafe_controls",
                    "header_affine_retained","header_invalidation_reason"):
            self.assertIn(key,GUEST)
            self.assertIn('"'+key+'"',HOST)
            self.assertIn('"'+key+'"',DIAG)
        self.assertNotIn("bundleIdentifier",GUEST.split(
            "static void ScarletIslandP44MonitorHeader(",1)[1].split(
            "static void ScarletIslandRepeatSurfaceToneCheck(",1)[0])

    def test_separate_p45_artifact_without_mutating_p44(self):
        self.assertIn('Scarlet-Crystal-V48-R6P45-SCROLL-PROOF-UNSIGNED.ipa',WORKFLOW)
        self.assertIn("scarlet-v48-r6p45-scroll-proof-unsigned-20261113",WORKFLOW)
        self.assertIn("scarlet-v48-r6p44-native-scroll-unsigned-20261113",WORKFLOW)
        self.assertIn("private func applyP43FallbackChrome",HOST)
        self.assertIn("chromeEligiblePIDs.insert(pid)",HOST)


if __name__=="__main__":
    unittest.main()
