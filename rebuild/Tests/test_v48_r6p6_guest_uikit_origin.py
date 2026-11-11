"""R6P6 root-cause geometry experiment: inspect guest UIKit, not host insets.

Source contracts only. Real Dynamic Island overlap and touch hit-testing
remain unverified until the exact signed build runs on an iPhone.
"""
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[1]
I = (R/"integration/apply_scarlet_host.py").read_text()
L = (R/"HostApp/ScarletGuestSessionLedger.swift").read_text()
D = (R/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
S = (R/"HostApp/ScarletFullscreenSceneStack.swift").read_text()

class GuestUIKitOriginProbe(unittest.TestCase):
    def test_samples_actual_guest_window_after_window_becomes_key(self):
        self.assertIn("SCARLET_GUEST_WINDOW_GEOMETRY_PROBE_V1", I)
        self.assertIn("if(NSUserDefaults.isLiveProcess) {", I)
        self.assertIn("UIWindowDidBecomeKeyNotification", I)
        self.assertIn("UIWindowDidBecomeVisibleNotification", I)
        self.assertIn("ScarletGuestWindowGeometryCapture(window", I)
        self.assertIn("dispatch_get_main_queue()", I)

    def test_records_both_owning_uikit_safeareas_and_statusbar(self):
        for value in ("window.safeAreaInsets.top", "rootView.safeAreaInsets.top",
                      "window.windowScene.statusBarManager.statusBarFrame",
                      "rootRect.origin.y", "window.windowScene.interfaceOrientation",
                      "controls_above_safe", "first_control_y"):
            self.assertIn(value, I)
        self.assertIn("inspected++ < 120", I)

    def test_shared_guest_only_numeric_payload_and_host_import(self):
        self.assertIn("Scarlet.Guest.WindowGeometry.V1", I)
        self.assertIn("Scarlet.Guest.WindowGeometry.V1", L)
        self.assertIn("guest_window_geometry_observed", L)
        self.assertIn("guest_liveprocess_uikit_window", L)
        self.assertIn("replayGuestWindowGeometryToHostJournal()", D)
        self.assertIn("epoch >= currentStart", L)
        self.assertIn("abs(number) <= 10000", L)
        self.assertIn('geometry_only": "true"', L)

    def test_not_another_inset_patch_or_guest_resize(self):
        probe = I.split("guest_layout_probe = r'''", 1)[1].split("\n'''", 1)[0]
        for forbidden in ("additionalSafeAreaInsets =", "safeAreaEdgeInsets =",
                          "setFrame:", "setTransform:", "statusBarDisabled =",
                          "peripheryInsets =", "setNeedsLayout", "layoutIfNeeded"):
            self.assertNotIn(forbidden, probe)
        self.assertIn("settings.peripheryInsets = UIEdgeInsetsZero;", I)
        self.assertIn("vc.scaleRatio = 1", S)
        self.assertIn("settings.setFrame(full)", S)

    def test_existing_audio_and_multitask_paths_present(self):
        self.assertIn("guest_audio_device_receipt", S)
        self.assertIn("home_audio_reactivation_suppressed", S)
        self.assertIn("fullscreen_scene_direct_switch", S)

if __name__ == "__main__":
    unittest.main()
