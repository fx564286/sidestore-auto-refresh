"""The initial landing page exposes both real engines and settings directly."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
PREVIEW=(ROOT/"PreviewHost/ScarletScreenshotPreviewApp.swift").read_text()
DESIGN=json.loads((ROOT/"design/figma-measured-baseline.json").read_text())
NAV=json.loads((ROOT/"config/scarlet-independent-ui-contract.json").read_text())["navigation"]
HOME=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]

class NativeHomeSettings(unittest.TestCase):
    def test_two_engine_cards_not_status_dashboard(self):
        self.assertEqual(HOME.count('engineEntry("'),2)
        self.assertIn('engineEntry("SideStore"',HOME)
        self.assertIn('engineEntry("가상 앱"',HOME)
        for redundant in ('"빠른 작업"','"최근 앱"','SCARLET_CENTERED_WORKSPACE_STATS','"활성 창"'):
            self.assertNotIn(redundant,HOME)
        self.assertEqual(DESIGN["design"]["alignment"]["homeAndSettings"]["engineEntryHeightsPt"],[78,78])

    def test_home_settings_simultaneously_visible_and_no_tab_on_landing(self):
        self.assertIn('heading("", "내 컨테이너", "")',HOME)
        self.assertNotIn('heading("", "설정", "")',HOME)
        self.assertNotIn('ScarletActionRow(title: "LiveContainer 전체 설정"',HOME)
        self.assertNotIn('if selected != .home {',UI)
        self.assertFalse(NAV["home_and_settings_inline"])
        self.assertFalse(NAV["home_tab_bar_hidden"])
        self.assertTrue(NAV["main_screen_requires_tab"])
        self.assertIn('case "settings": startTab = .settings',PREVIEW)

    def test_no_faux_settings_just_original_livecontainer_and_sidestore(self):
        self.assertNotIn('.sheet(isPresented: $showLocalAppearance)',UI)
        self.assertNotIn('.sheet(isPresented: $showLocalStorage)',UI)
        self.assertNotIn('onAction(.localAppearance)',HOME)
        self.assertIn('onAction(.localAppearance)',UI)
        self.assertIn('onAction(.localOpenEmbeddedSideStore)',HOME)
        self.assertIn('onAction(.localImportGuestIPA)',HOME)
        for literal in ("LCSettingsView()","LCAppListView()",
                        "LCUtils.openSideStore(delegate: nil)"):
            self.assertIn(literal,HOST)
        self.assertIn("case .localAppearance, .localStorageNavigation",HOST)
        self.assertIn(".serviceBeginSignIn,",HOST)
        self.assertNotIn("clearAppGroup",UI)

if __name__=="__main__":
    unittest.main()
