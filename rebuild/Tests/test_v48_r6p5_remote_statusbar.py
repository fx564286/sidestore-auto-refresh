"""R6P5 native remote FBScene status-bar layout contracts.

These are source/compile checks; only an iPhone screenshot + touch test can
verify Instagram's actual title position and Dynamic Island avoidance.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = (ROOT/"integration/apply_scarlet_host.py").read_text()
HOST = (ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
STACK = (ROOT/"HostApp/ScarletFullscreenSceneStack.swift").read_text()


class PilotStatusBarLayoutTests(unittest.TestCase):
    def test_status_bar_comes_from_actual_uiwindowscene(self):
        self.assertIn("static CGRect ScarletPilotHostStatusBarFrame(UIWindowScene *scene)", INTEGRATION)
        self.assertIn("hostScene.statusBarManager.statusBarFrame", INTEGRATION)
        self.assertIn("UISceneActivationStateForegroundActive", INTEGRATION)
        self.assertIn("isfinite(bar.size.height)", INTEGRATION)

    def test_scene_status_bar_metadata_is_applied_at_initial_and_live_stages(self):
        self.assertEqual(INTEGRATION.count("CGRect bar = ScarletPilotHostStatusBarFrame("), 2)
        self.assertEqual(INTEGRATION.count("settings.statusBarHeight = CGRectGetHeight(bar);"), 2)
        self.assertEqual(INTEGRATION.count("settings.statusBarAvoidanceFrame = bar;"), 2)
        self.assertEqual(INTEGRATION.count("if(settings.statusBarHeight <= 0)"), 2)
        self.assertEqual(INTEGRATION.count("if(CGRectIsEmpty(settings.statusBarAvoidanceFrame))"), 2)

    def test_pilot_only_and_full_bleed_not_rescaled(self):
        self.assertIn("if(self.scarletNativeFullscreenSlot) {", INTEGRATION)
        self.assertIn("if(scarletPilot) {", INTEGRATION)
        self.assertIn("settings.peripheryInsets = UIEdgeInsetsZero;", INTEGRATION)
        self.assertNotIn("settings.peripheryInsets = safe;", INTEGRATION)
        self.assertIn("vc.scaleRatio = 1", STACK)
        self.assertIn("settings.setFrame(full)", STACK)
        self.assertIn("safe = SCGeometryResolve(self, safe, settings.interfaceOrientation", INTEGRATION)

    def test_real_remote_scene_metadata_reported_without_claiming_visual_success(self):
        self.assertIn('@"status_bar_height": @(settings.statusBarHeight)', INTEGRATION)
        self.assertIn('@"avoidance_max_y": @(CGRectGetMaxY(settings.statusBarAvoidanceFrame))', INTEGRATION)
        self.assertIn('"status_bar_height_pt": String(barHeight)', HOST)
        self.assertIn('"status_bar_avoidance_max_y_pt": String(avoidanceBottom)', HOST)
        self.assertNotIn("optical_verified = true", HOST)

    def test_existing_guest_audio_and_switcher_untouched(self):
        self.assertIn("home_audio_reactivation_suppressed", STACK)
        self.assertIn("guest_audio_device_receipt", STACK)
        self.assertIn("resident_host_background_tap_received", STACK)


if __name__ == "__main__":
    unittest.main()
