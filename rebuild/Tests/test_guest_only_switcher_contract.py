"""Guest-only circular switcher, owned runtime screenshots, no static images."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
GUEST=(ROOT/"HostApp/ScarletGuestSwitcherOverlay.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()
PREVIEW=(ROOT/"PreviewHost/ScarletScreenshotPreviewApp.swift").read_text()
CONFIG=json.loads((ROOT/"config/scarlet-independent-ui-contract.json").read_text())

class GuestOnlySwitcherContract(unittest.TestCase):
    def test_container_has_no_round_switcher(self):
        for text in (UI,HOST,PREVIEW):
            self.assertNotIn("preservedGlassSwitchControl",text)
            self.assertNotIn("SCARLET_SINGLE_ROUND_APP_SWITCHER",text)
        self.assertNotIn("ScarletNativeGlassSwitcher(",HOST)
        self.assertEqual(CONFIG["navigation"]["round_switcher_visibility"],"guest_scene_only")
        self.assertFalse(CONFIG["navigation"]["container_shell_has_round_switcher"])

    def test_guest_app_scene_owns_switcher_and_live_preview(self):
        for text in ("ScarletGuestSwitcherOverlay(dataUUID: appInfo.dataUUID",
                     "ScarletGuestSceneRegistry.register(controller, dataUUID: dataUUID)",
                     "ScarletGuestSceneRegistry.unregister(dataUUID)"):
            self.assertIn(text,PATCH)
        for text in ("SCARLET_GUEST_ONLY_ROUND_SWITCHER",
                     "SCARLET_GUEST_OUTSIDE_TAP_DISMISS",
                     "drawHierarchy(in: bounds, afterScreenUpdates: false)",
                     "Image(uiImage: image)",
                     "ScarletGuestSceneRegistry.availableGuests()",
                     "ScarletGuestSceneRegistry.activate(item.id)",
                     "SCARLET_LIVE_GUEST_PREVIEW_ROW"):
            self.assertIn(text,GUEST)
        self.assertNotIn('Image("Madeira")',GUEST)
        self.assertNotIn("Figma.png",GUEST)
        self.assertNotIn("UIImage(named:",GUEST)
        self.assertIn("SCNativeLiquidGlassSurface",GUEST)
        self.assertIn("UIGraphicsImageRenderer(size: output, format: format)",GUEST)
        self.assertIn("ScarletGuestListCard",UI)
        self.assertIn("ScarletStatusBadge",UI)
        self.assertIn(".frame(height: 44)",UI)
        self.assertIn("isRunning: visible",HOST)
        self.assertIn("ScarletNativeGlassSwitcher(openManager:",GUEST)

    def test_host_builder_copies_guest_source(self):
        self.assertIn('"ScarletGuestSwitcherOverlay.swift"', PATCH)
        self.assertIn('guest_window.write_text(guest_src)', PATCH)

if __name__ == "__main__":
    unittest.main()
