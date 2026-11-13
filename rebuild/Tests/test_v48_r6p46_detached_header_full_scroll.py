"""R6P46: prevent stale UI header reference from cropping the full scroll scene.

Signed P45 PID5066 had a successful transformed header 8->5 followed by
reason1 (header.window detached, zero controls), causing unnecessary
host FBScene y62/h894. These tests enforce a materially different rule:
reconcile CURRENT root severe visible hit targets before invalidating.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
G=(ROOT/"integration/ScarletGuestIslandContentGuard.m.txt").read_text()
H=(ROOT/"HostApp/ScarletFullscreenSceneStack.swift").read_text()
D=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
W=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()


class DetachedHeaderScrollProof(unittest.TestCase):
    def test_detach_does_not_automatically_crop_remote(self):
        monitor=G.split("static void ScarletIslandP44MonitorHeader(UIWindow *window) {",1)[1].split(
            "static void ScarletIslandRepeatSurfaceToneCheck(",1)[0]
        self.assertIn("if(!attached) {",monitor)
        self.assertIn("if(ScarletIslandP46HandleDetached(window,top,YES))",monitor)
        self.assertIn("continue;",monitor)
        self.assertIn("if(headers.count==0 &&",monitor)
        self.assertIn("ScarletIslandP46HandleDetached(window,top,NO)",monitor)

    def test_native_unsafe_current_geometry_is_measured_not_assumed(self):
        body=G.split("static NSInteger ScarletIslandP46CurrentSevereControls(\n    UIWindow *window, CGFloat safeTop, NSInteger *firstY,\n    NSUInteger *visibleControls) {",1)[1].split(
            "// R6P34: the signed P33 owner",1)[0]
        self.assertIn("ScarletIslandWalkViews(root,window,safeTop,0,&metrics,groups)",body)
        self.assertIn("ScarletIslandVisibleFrameInWindow(control,window)",body)
        self.assertIn("CGRectGetMinY(shown)>=safeTop-15",body)
        self.assertIn("root.safeAreaInsets.top-safeTop",body)
        self.assertIn("metrics.firstUnsafeControlY<safeTop-15 && severe==0",body)
        self.assertIn("return -1;",body)

    def test_temporary_detachment_or_safe_controls_preserve_full_scene(self):
        body=G.split("static BOOL ScarletIslandP46HandleDetached(",1)[1].split(
            "static void ScarletIslandP44MonitorHeader(",1)[0]
        self.assertIn("if(severe<0)",body)
        self.assertIn("if(severe==0)",body)
        self.assertIn('@"guest_header_detached_probe_deferred"',body)
        self.assertIn('@"guest_header_detached_fullscene_retained"',body)
        self.assertIn("return YES;",body)
        self.assertNotIn("setFrame(",body)
        self.assertNotIn("contentInset=",body)
        self.assertNotIn("contentOffset=",body)

    def test_proven_current_severe_controls_require_repeat_before_fallback(self):
        body=G.split("static BOOL ScarletIslandP46HandleDetached(",1)[1].split(
            "static void ScarletIslandP44MonitorHeader(",1)[0]
        self.assertIn("if(severe<2)",body)
        self.assertIn("if(samples<1)",body)
        self.assertIn('@"guest_header_detached_risk_provisional"',body)
        self.assertIn('@"guest_header_detached_risk_confirmed"',body)
        self.assertIn("return NO;",body)
        self.assertIn("scarletIslandP46DetachedRiskSamplesKey",body)

    def test_recycled_controls_reconcile_instead_of_false_failing(self):
        monitor=G.split("static void ScarletIslandP44MonitorHeader(UIWindow *window) {",1)[1].split(
            "static void ScarletIslandRepeatSurfaceToneCheck(",1)[0]
        self.assertIn("if(attached && affineRetained && checked<2 &&",monitor)
        self.assertIn("ScarletIslandP46HandleDetached(window,top,YES)",monitor)
        self.assertIn('if(affineRetained)\n            header.transform=CGAffineTransformIdentity;',monitor)

    def test_anonymous_device_telemetry_and_host_callback(self):
        for k in ("header_detached_severe", "header_detached_first_y",
                  "header_detached_visible_controls", "header_detached_samples"):
            self.assertIn('"'+k+'"',G)
            self.assertIn('"'+k+'"',H)
            self.assertIn('"'+k+'"',D)
        self.assertIn("guest_header_detached_fullscene_retained",H)
        self.assertIn('result == "guest_header_local_transform_invalidated"',H)
        self.assertNotIn("onHeaderTransformVerified?(pid, false)\n                } else if result == \"guest_header_detached_fullscene_retained\"",H)

    def test_p46_separate_release_preserves_p45_code_and_unmodified_fallback(self):
        self.assertIn("Scarlet-Crystal-V48-R6P46-DETACHED-FULL-SCROLL-UNSIGNED.ipa",W)
        self.assertIn("scarlet-v48-r6p46-detached-full-scroll-unsigned-20261113",W)
        self.assertIn("scarlet-v48-r6p45-scroll-proof-unsigned-20261113",W)
        self.assertIn("private func applyP43FallbackChrome",H)
        self.assertIn("guest_header_local_transform_retained",G)
        self.assertNotIn('bundleID == "com.burbn.instagram"',H)


if __name__ == '__main__':
    unittest.main()
