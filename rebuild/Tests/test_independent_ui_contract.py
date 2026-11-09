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
HOME=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]

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
        self.assertEqual(HOME.count("\n                Menu {"),1)
        self.assertNotIn(".contextMenu {",HOME)
        self.assertIn('Label("IPA 설치하기"',HOME)
        self.assertLess(HOME.index("Menu {"), HOME.index("onAction(.localImportGuestIPA)"))
        self.assertIn("onAction(.serviceInstallIPA)",HOME)
        self.assertIn("onAction(.localImportGuestIPA)",HOME)
        self.assertIn("ForEach(visibleGuests) { guest in",HOME)
        self.assertIn("SCARLET_APPS_FOUR_COLUMN_LAUNCHER",HOME)
        self.assertIn("count: 4",HOME)
        self.assertNotIn("ScarletGuestListCard(",HOME)
        self.assertEqual(HOME.count("onAction(.serviceInstallIPA)"),1)
        self.assertEqual(HOME.count("onAction(.localImportGuestIPA)"),1)
        self.assertNotIn("installPathRow(",UI)
        self.assertNotIn("guests: Array(guests.prefix(5))",HOME)
        self.assertNotIn("private var apps: some View",UI)

    def test_exactly_four_native_glass_tab_destinations(self):
        self.assertIn("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR",UI)
        self.assertEqual(UI.count("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR"),1)
        for marker in ('case sources = "소스"','case apps = "앱"',
                       'case tweaks = "트윅"','case settings = "설정"'):
            self.assertIn(marker,UI)
        self.assertNotIn('case home = "Home"',UI)
        self.assertEqual(CONTRACT["navigation"]["bottom_tabs"],
                         ["sources","apps","tweaks","settings"])
        self.assertEqual(CONTRACT["navigation"]["bottom_tab_display_labels"],
                         ["소스","앱","트윅","설정"])
        self.assertEqual(CONTRACT["navigation"]["initial_screen"],"apps")
        self.assertIn("initialTab: Tab = .apps",UI)
        self.assertIn("preservedGlassTabBar($selected)",UI)
        self.assertIn("preservedGlassTabBar: (Binding<Tab>) -> AnyView",UI)
        self.assertNotIn(".glassEffect(",UI)
        self.assertNotIn("case windowManager",UI)
        self.assertNotIn("SCARLET_SINGLE_ROUND_APP_SWITCHER",UI)

    def test_sources_still_uses_existing_source_models(self):
        self.assertIn("public let sources: [ScarletSourcePresentation]",UI)
        self.assertIn("if tab == .sources {",UI)
        self.assertIn('heading("", "소스", "")',UI)
        self.assertIn("Button(action: onAddSource)",UI)
        self.assertIn("LCSourcesView()",HOST)

    def test_tweaks_tab_embeds_real_livecontainer_manager_without_new_modal(self):
        self.assertIn("if tab == .tweaks {",UI)
        self.assertIn("nativeTweaks()",UI)
        self.assertIn("SCARLET_INLINE_NATIVE_LC_TWEAKS",UI)
        self.assertIn("LCTweaksView()",HOST)
        self.assertIn("nativeTweaks: {",HOST)
        self.assertTrue(CONTRACT["navigation"]["reference_screenshot_scope"].startswith("BOTTOM TABS"))
        self.assertNotIn(".glassEffect(",UI)

    def test_settings_tab_shows_native_form_without_same_sheet_for_all_controls(self):
        self.assertIn("if tab == .settings {",UI)
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
        INTEGRATOR=(ROOT/"integration/apply_scarlet_host.py").read_text()
        self.assertIn("SCARLET_SETTINGS_NATIVE_APPLE_LOGIN",INTEGRATOR)
        self.assertIn("case .serviceBeginSignIn:",HOST)
        self.assertIn("ScarletDiagnosticLogView()",INTEGRATOR)
        self.assertNotIn('Text("설정")',UI)
        self.assertTrue(CONTRACT["navigation"]["signin_request_requires_verified_engine"])
        self.assertIn("One actor",CORE)

    def test_responsive_safe_area_and_no_source_data_deletion(self):
        for marker in ("ScrollView","ForEach","TextField","Button",
                       ".frame(maxWidth: 650, alignment: .leading)",
                       ".padding(.horizontal, 20)","accessibilityIdentifier"):
            self.assertIn(marker,UI)
        self.assertNotIn("UIScreen.main.bounds",UI)
        self.assertNotIn("UIWindow(",UI)
        # Only the copied temporary IPA can be cleaned, not the Files original.
        self.assertIn("startAccessingSecurityScopedResource()",HOST)
        self.assertIn("FileManager.default.copyItem(at: source, to: temporary)",HOST)
        self.assertIn("private func guestImportWorkerFinished()",HOST)
        self.assertIn("try? FileManager.default.removeItem(at: staged)",HOST)
        self.assertIn("queuedGuestIPAURL = nil",HOST)
        self.assertNotIn("removeItem(at: source)",HOST)
        self.assertNotIn("removeItem(at: selected)",HOST)
        self.assertIn("try await app.runApp()",HOST)

if __name__=="__main__":
    unittest.main()
