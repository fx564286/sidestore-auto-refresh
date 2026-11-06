"""User-approved single Home + native Settings integration contracts.

Static checks validate source intent, not signed-device SideSign readiness.
"""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=json.loads((ROOT/"config/scarlet-independent-ui-contract.json").read_text())
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
CORE=(ROOT/"Sources/ScarletCleanCore/ScarletActionCoordinator.swift").read_text()
HOME=UI[UI.index("    private var home: some View {"):UI.index("    private func installPathRow(")]

class IndependentUIContractTests(unittest.TestCase):
    def test_pinned_identity_and_engine_boundaries(self):
        self.assertEqual([x["id"] for x in CONTRACT["protected_runtime"]],
                         ["liquid_glass","livecontainer_engine","sidestore","sidesign"])
        self.assertEqual(CONTRACT["preserved_identity"]["bundle_id"],
                         "com.kdt.livecontainer.P8EZT3U5N4")
        self.assertEqual(CONTRACT["preserved_identity"]["team_id"],"P8EZT3U5N4")
        self.assertTrue(CONTRACT["preserved_identity"]["keep_existing_app_groups"])
        self.assertTrue(CONTRACT["preserved_identity"]["keep_guest_and_host_data"])

    def test_no_legacy_router_or_fake_glass(self):
        for forbidden in ("V3UnifiedShell","V3ServiceBridge","LiveProcessService",
                          "SideSignManager","import SideStore","import LiveContainer",
                          ".glassEffect(","clearAppGroup","removeUserData",
                          "revokeCertificate","nukeSideStore"):
            self.assertNotIn(forbidden,UI)
        self.assertIn("struct ScarletIndependentShell",UI)
        self.assertIn("struct ScarletHostPresentationSnapshot",UI)

    def test_only_one_home_with_two_distinct_install_engines(self):
        self.assertIn('heading("", "설치된 앱", "")',HOME)
        self.assertEqual(HOME.count('installPathRow("'),2)
        self.assertIn('installPathRow("SideStore 앱 설치"',HOME)
        self.assertIn('installPathRow("게스트 앱 설치"',HOME)
        self.assertIn("onAction(.serviceInstallIPA)",HOME)
        self.assertIn("onAction(.localImportGuestIPA)",HOME)
        self.assertIn("guests: visibleGuests",HOME)
        self.assertNotIn("guests: Array(guests.prefix(5))",HOME)
        self.assertNotIn("private var apps: some View",UI)

    def test_exactly_three_native_glass_tab_destinations(self):
        self.assertIn("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR",UI)
        self.assertEqual(UI.count("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR"),1)
        for marker in ('case home = "Home"','case sources = "Sources"',
                       'case settings = "Settings"'):
            self.assertIn(marker,UI)
        self.assertNotIn('case apps = "Apps"',UI)
        self.assertEqual(CONTRACT["navigation"]["bottom_tabs"],
                         ["home","sources","settings"])
        self.assertIn("preservedGlassTabBar($selected)",UI)
        self.assertIn("preservedGlassTabBar: (Binding<Tab>) -> AnyView",UI)
        self.assertNotIn(".glassEffect(",UI)
        self.assertNotIn("case windowManager",UI)
        self.assertNotIn("SCARLET_SINGLE_ROUND_APP_SWITCHER",UI)

    def test_sources_still_uses_existing_source_models(self):
        self.assertIn("public let sources: [ScarletSourcePresentation]",UI)
        self.assertIn("case .sources: sourcesScreen",UI)
        self.assertIn('heading("", "소스", "")',UI)
        self.assertIn("Button(action: onAddSource)",UI)
        self.assertIn("LCSourcesView()",HOST)

    def test_settings_tab_shows_native_form_without_same_sheet_for_all_controls(self):
        self.assertIn("if selected == .settings {",UI)
        self.assertIn("nativeSettings()",UI)
        self.assertIn("SCARLET_INLINE_NATIVE_LC_SETTINGS",UI)
        self.assertIn("LCSettingsView()",HOST)
        self.assertIn("nativeSettings: {",HOST)
        self.assertNotIn(".sheet(isPresented: $showNativeSettings)",HOST)
        self.assertNotIn('ScarletActionRow(title: "화면 설정"',UI)
        self.assertNotIn('ScarletActionRow(title: "저장소"',UI)
        self.assertNotIn('ScarletActionRow(title: "진단 로그"',UI)
        self.assertNotIn("showConnectionDetails",UI)
        self.assertTrue(CONTRACT["navigation"]["settings_tab_inline_native"])

    def test_auth_status_not_confused_with_engine_presence(self):
        for field in ("appleAuthenticated: Bool","pairingVerified: Bool",
                      "installationVerified: Bool","signingVerified: Bool"):
            self.assertIn(field,UI)
        self.assertIn("SCARLET_SETTINGS_NATIVE_APPLE_LOGIN",UI)
        self.assertIn("onAction(.serviceBeginSignIn)",UI)
        self.assertTrue(CONTRACT["navigation"]["signin_request_requires_verified_engine"])
        self.assertIn("One actor",CORE)

    def test_responsive_safe_area_and_no_source_data_deletion(self):
        for marker in ("ScrollView","ForEach","TextField","Button",
                       ".frame(maxWidth: 650, alignment: .leading)",
                       ".padding(.horizontal, 20)","accessibilityIdentifier"):
            self.assertIn(marker,UI)
        self.assertNotIn("UIScreen.main.bounds",UI)
        self.assertNotIn("UIWindow(",UI)
        self.assertNotIn("removeItem(at:",HOST)
        self.assertIn("try await app.runApp()",HOST)

if __name__=="__main__":
    unittest.main()
