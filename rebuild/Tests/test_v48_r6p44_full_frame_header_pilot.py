"""P44 source contract: keep 1:1 native remote scroll scene and move only proven header.

Static tests cannot substitute for a signed iPhone render or UIKit hit-testing.
"""
from pathlib import Path
import unittest

BASE = Path(__file__).resolve().parents[1]
HOST = (BASE / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
GUEST = (BASE / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()


class P44NativeHeaderPilot(unittest.TestCase):
    def test_full_native_scene_while_guest_pilot_is_pending(self):
        a = HOST.index("private func onUnsafeGuestControls(")
        b = HOST.index("private func applyP43FallbackChrome(", a)
        body = HOST[a:b]
        self.assertIn("chromePendingFallbackPIDs.insert(pid)", body)
        self.assertIn("DispatchQueue.main.asyncAfter(deadline: .now() + 2.4)", body)
        self.assertIn("onNativeHeaderTransform(pid:", body)
        self.assertIn("chromeHeaderProtectedPIDs.insert(pid)", body)
        self.assertIn("chromeEligiblePIDs.remove(pid)", body)
        self.assertIn("updateNativeChromeSlots(scene)", body)
        self.assertIn("chromePendingFallbackPIDs.remove(pid)", body)
        self.assertIn("!self.chromeHeaderProtectedPIDs.contains(pid)", body)

    def test_only_the_short_header_is_translated_not_the_scroll_scene(self):
        body = GUEST.split("static void ScarletIslandTryP44LocalHeaderTransform(", 2)[-1]
        body = body.split("static void ScarletIslandTryDeepHeaderSafeGuideAnchor(", 1)[0]
        self.assertIn("header.transform=CGAffineTransformTranslate(original,0,safeTop)", body)
        for immutable in ("window.frame=", "root.frame=", "contentInset=",
                          "contentOffset=", "setFrame:", "setFrame(",
                          "header.frame=", "scroll.transform="):
            self.assertNotIn(immutable, body)
        for safe in ("severe<2", "fabs(CGRectGetWidth(cursor.bounds)-",
                     "CGAffineTransformIsIdentity(cursor.transform)",
                     "ScarletIslandDeepHeaderOwnerReady(",
):
            self.assertIn(safe, body)
        self.assertIn("window.windowLevel!=UIWindowLevelNormal", body)
        self.assertIn("window.windowScene.activationState!=UISceneActivationStateForegroundActive", body)

    def test_header_probe_and_two_verified_readbacks(self):
        self.assertIn("ScarletIslandTryP44LocalHeaderTransform(\n        window, rootView", GUEST)
        self.assertIn('@"guest_header_local_transform_first_pass"', GUEST)
        self.assertIn('@"guest_header_local_transform_retained"', GUEST)
        self.assertIn('@"guest_header_local_transform_reverted"', GUEST)
        self.assertIn("unsafe+2<=beforeControls", GUEST)
        self.assertIn("images<=beforeImages+1", GUEST)
        self.assertIn("ScarletIslandVisibleFrameInWindow(one,w)", GUEST)
        self.assertIn("ScarletIslandVisibleFrameInWindow(two,w)", GUEST)
        self.assertIn("head.transform=original", GUEST)
        self.assertIn("readback=nil;", GUEST)

    def test_on_reentry_detect_visual_header_invalidations(self):
        self.assertIn("static void ScarletIslandP44MonitorHeader(", GUEST)
        self.assertIn("ScarletIslandP44MonitorHeader(current);", GUEST)
        self.assertIn('@"guest_header_local_transform_invalidated"', GUEST)
        self.assertIn("onHeaderTransformVerified?(pid, false)", HOST)
        self.assertIn("chromeHeaderProtectedPIDs.remove(pid)", HOST)

    def test_p43_untouched_fallback_and_safe_guests(self):
        self.assertIn("private func applyP43FallbackChrome(", HOST)
        self.assertIn("chromeEligiblePIDs.insert(pid)", HOST)
        self.assertIn("let top = reserved ? chromeTop(in: scene) : 0", HOST)
        self.assertIn("settings.setFrame(rect)", HOST)
        self.assertIn("vc.scaleRatio = 1", HOST)
        self.assertIn("chromeHeaderProtectedPIDs.remove(old.pid)", HOST)
        self.assertIn("chromePendingFallbackPIDs.remove(old.pid)", HOST)
        self.assertNotIn('bundleID == "com.burbn.instagram"', HOST)
        self.assertNotIn("[UIApplication sharedApplication]", GUEST)
        self.assertNotIn("UIApplication.sharedApplication]", GUEST)

    def test_native_render_validation_not_assumed_from_static_test(self):
        # Full-screen only wins if the real guest reports both readbacks;
        # the source alone cannot claim actual iPhone visual/touch success.
        self.assertIn("onHeaderTransformVerified?(pid, true)", HOST)
        self.assertIn("guest_fullscreen_header_verified", HOST)
        self.assertIn("p43_fallback_after_header_pilot", HOST)
        self.assertIn("resident_transparent_chrome_slot", HOST)


if __name__ == "__main__":
    unittest.main()
