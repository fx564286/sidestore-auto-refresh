"""Native IPA catalog visually mirrors the guest launcher without mixing ownership."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()

class NativeGuestLauncherParityTests(unittest.TestCase):
    def test_both_registries_share_grid_column_geometry(self):
        self.assertEqual(UI.count("columns: launcherColumns,"), 2)
        self.assertEqual(UI.count("alignment: .center, spacing: 28"), 2)
        self.assertEqual(UI.count(".padding(.top, 16)"), 2)
        self.assertIn("count: 4)", UI)
        self.assertIn("SCARLET_DEVICE_APPS_FOUR_COLUMN_LAUNCHER", UI)
        self.assertIn("SCARLET_APPS_FOUR_COLUMN_LAUNCHER", UI)

    def test_shared_icon_frame_corner_and_title_renderer(self):
        self.assertEqual(UI.count("private struct ScarletLauncherArtwork"), 1)
        self.assertEqual(UI.count("private struct ScarletLauncherCaption"), 1)
        self.assertIn(".frame(width: 66, height: 66)", UI)
        self.assertIn("RoundedRectangle(cornerRadius: 16", UI)
        guest=UI.split("private struct ScarletGuestLauncherTile: View {")[1].split(
            "private struct ScarletManagedDeviceLauncherTile: View {")[0]
        native=UI.split("private struct ScarletManagedDeviceLauncherTile: View {")[1].split(
            "@available(iOS 16.0, *)")[0]
        for view in (guest,native):
            self.assertIn("ScarletLauncherArtwork(",view)
            self.assertIn("ScarletLauncherCaption(",view)
        self.assertNotIn("ScarletPanel {\n                    ForEach(visibleDeviceApps)", UI)

    def test_gestures_stay_owner_scoped(self):
        native=UI.split("private struct ScarletManagedDeviceLauncherTile: View {")[1].split(
            "@available(iOS 16.0, *)")[0]
        self.assertIn("Button(action: onManage)", native)
        self.assertNotIn("onOpenGuest",native)
        self.assertNotIn("onDeleteGuest",native)
        self.assertIn("SCARLET_DEVICE_MANAGED_IPA_ROW",native)
        self.assertIn("onManage: onManageDeviceApps",UI)
        self.assertIn("SCARLET_GUEST_UNINSTALL_MENU", UI)
        self.assertIn("await ScarletNativeSideloadSlots.list()",HOST)
        self.assertIn("deviceApps: managedDeviceApps",HOST)
        self.assertIn("ForEach(visibleDeviceApps) { app in", UI)
        self.assertIn("ForEach(visibleGuests) { guest in", UI)

    def test_native_record_is_not_claimed_as_springboard_install(self):
        self.assertIn("SideStore 관리 중", UI)
        self.assertIn("비활성 관리 기록", UI)
        self.assertNotIn("installation_verified=true",UI)

if __name__ == "__main__":
    unittest.main()
