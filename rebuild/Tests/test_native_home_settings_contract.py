"""Current Home and Settings behavior: one screen per tab and real engine surfaces."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
PREVIEW=(ROOT/"PreviewHost/ScarletScreenshotPreviewApp.swift").read_text()
NAV=json.loads((ROOT/"config/scarlet-independent-ui-contract.json").read_text())["navigation"]
HOME=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]

class NativeHomeSettings(unittest.TestCase):
    def test_one_home_both_install_targets_and_entire_guest_list(self):
        self.assertEqual(HOME.count("\n                Menu {"),1)
        self.assertIn('Label("IPA 설치하기"',HOME)
        self.assertIn('onAction(.localImportGuestIPA)',HOME)
        self.assertIn("guests: visibleGuests",HOME)
        self.assertIn("SCARLET_INSTALL_CHOICE_DEVICE_IPA",HOME)
        self.assertNotIn(".contextMenu {",HOME)
        self.assertIn("SCARLET_INSTALL_CHOICE_GUEST_APP",HOME)
        self.assertEqual(NAV["bottom_tabs"],["sources","apps","tweaks","settings"])
        self.assertEqual(NAV["initial_screen"],"apps")
        self.assertIn("initialTab: Tab = .apps",UI)
        self.assertNotIn('private var apps: some View {',UI)
        self.assertNotIn("installPathRow(",UI)
        self.assertEqual(HOME.count("onAction(.serviceInstallIPA)"),1)
        self.assertEqual(HOME.count("onAction(.localImportGuestIPA)"),1)

    def test_settings_tab_direct_native_not_an_extra_modal(self):
        self.assertIn("if selected == .settings {",UI)
        self.assertIn("nativeSettings()",UI)
        self.assertIn("LCSettingsView()",HOST)
        self.assertIn("LCTweaksView()",HOST)
        self.assertIn("nativeTweaks()",UI)
        self.assertNotIn(".sheet(isPresented: $showNativeSettings)",HOST)
        self.assertNotIn("showNativeSettings = true",HOST)
        self.assertNotIn("showConnectionDetails",UI)
        self.assertTrue(NAV["settings_tab_inline_native"])
        self.assertIn('case "settings", "connection": startTab = .settings',PREVIEW)

    def test_original_guest_import_and_side_store_fenced(self):
        self.assertIn(".fileImporter(isPresented: $showGuestFilePicker,",HOST)
        self.assertIn("LCAppListView(scarletQueuedIPAURL: queuedGuestIPAURL,",HOST)
        self.assertNotIn("showNativeAppLibrary",HOST)
        self.assertIn("prepareDeviceIPAInstall(selected)",HOST)
        self.assertIn("case .localImportGuestIPA:",HOST)
        self.assertIn("case .serviceInstallIPA:",HOST)
        self.assertNotIn("LCUtils.openSideStore(",HOST)
        self.assertNotIn("clearAppGroup",HOST)

if __name__=="__main__":
    unittest.main()
