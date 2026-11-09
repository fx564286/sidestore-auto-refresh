"""Regression for both LiveContainer native and virtual guest exit routes."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
SWITCHER=(ROOT/"HostApp/ScarletGuestSwitcherOverlay.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()

class GuestExitLifecycle(unittest.TestCase):
    def test_guest_launch_routes_into_owned_multitask_scene(self):
        self.assertIn("try await app.runApp(multitask: true)",HOST)
        self.assertIn('defaultClassicMode == 0',HOST)
        self.assertIn('classic_mode_has_no_exit_control',HOST)
        self.assertNotIn("try await app.runApp()\\n",HOST)

    def test_native_close_disposes_scene_not_guest_data(self):
        for code in ("exitCurrentGuestAndReturnToScarlet()",
                     'openWindow(id: "Main")',
                     'requestSceneDestruction(isManual: true)',
                     "ScarletGuestSceneRegistry.unregister(info.dataUUID)",
                     "MultitaskWindowManager.appDict.removeValue(forKey: info.dataUUID)"):
            self.assertIn(code,PATCH)
        self.assertNotIn("FileManager.default.removeItem",SWITCHER)
        self.assertNotIn("LCCertificateData",SWITCHER)

    def test_virtual_close_calls_real_upstream_close_window(self):
        self.assertIn("DecoratedAppSceneViewController.m",PATCH)
        self.assertIn("ScarletGuestOverlayInstaller installOnController:self",PATCH)
        self.assertIn('[self closeWindow];',PATCH)
        self.assertIn('scarletExitToHost',SWITCHER)
        self.assertIn("width.constant = expanded ?",SWITCHER)
        self.assertIn('ScarletGuestSceneRegistry.availableGuests()',SWITCHER)
        self.assertIn("SCARLET_LIVE_GLASS_SWITCHER_MATERIAL",
                      (ROOT/"HostApp/ScarletNativeGlass.swift").read_text())

if __name__=="__main__":unittest.main()
