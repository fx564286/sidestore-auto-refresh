"""Scarlet Crystal clean UI acceptance contract (no app installation)."""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=json.loads((ROOT/"config/scarlet-independent-ui-contract.json").read_text())
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
CORE=(ROOT/"Sources/ScarletCleanCore/ScarletActionCoordinator.swift").read_text()


class IndependentUIContractTests(unittest.TestCase):
    def test_keep_only_four_runtime_dependencies(self):
        self.assertEqual([x["id"] for x in CONTRACT["protected_runtime"]],
                         ["liquid_glass","livecontainer_engine","sidestore","sidesign"])
        self.assertEqual(CONTRACT["preserved_identity"]["bundle_id"],
                         "com.kdt.livecontainer.P8EZT3U5N4")
        self.assertEqual(CONTRACT["preserved_identity"]["team_id"],"P8EZT3U5N4")
        self.assertTrue(CONTRACT["preserved_identity"]["keep_existing_app_groups"])
        self.assertTrue(CONTRACT["preserved_identity"]["keep_guest_and_host_data"])
        self.assertIn("figma.com/design/",CONTRACT["design_file"])

    def test_full_ui_not_bound_to_legacy_v3(self):
        for forbidden in ("V3UnifiedShell","V3ServiceBridge","LiveProcessService",
                          "SideSignManager","import SideStore","import LiveContainer",
                          ".glassEffect(", "clearAppGroup", "removeUserData",
                          "revokeCertificate", "nukeSideStore"):
            self.assertNotIn(forbidden,UI)
        self.assertNotIn("preservedGlassSwitchControl",UI)
        self.assertIn("struct ScarletIndependentShell",UI)
        self.assertIn("struct ScarletHostPresentationSnapshot",UI)

    def test_home_settings_creation_rolled_back_and_engine_targets_preserved(self):
        h=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]
        self.assertIn('engineEntry("SideStore"',h)
        self.assertIn('engineEntry("가상 앱"',h)
        self.assertIn('onAction(.localOpenEmbeddedSideStore)',h)
        self.assertIn('onAction(.localImportGuestIPA)',h)
        self.assertNotIn('onAction(.localAppearance)',h)
        self.assertNotIn('heading("", "설정", "")',h)
        self.assertIn('heading("", "설정", "")',UI)
        self.assertNotIn("if selected != .home {",UI)
        self.assertNotIn('showLocalAppearance = true',UI)
        self.assertNotIn('showLocalStorage = true',UI)
        self.assertNotIn('Text("실제 설정값은 기존 앱의 로컬 설정 저장소에 연결해야 합니다.")',UI)

    def test_native_glass_bottom_tabs_and_single_round_switcher(self):
        self.assertIn("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR", UI)
        self.assertNotIn("SCARLET_SINGLE_ROUND_APP_SWITCHER", UI)
        self.assertEqual(UI.count("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR"), 1)
        self.assertEqual(UI.count("SCARLET_SINGLE_ROUND_APP_SWITCHER"), 0)
        self.assertIn("preservedGlassTabBar: (Binding<Tab>) -> AnyView", UI)
        self.assertIn("preservedGlassTabBar: @escaping (Binding<Tab>) -> AnyView", UI)
        self.assertIn("preservedGlassTabBar($selected)", UI)
        self.assertNotIn("preservedGlassSwitchControl: AnyView", UI)
        self.assertNotIn(".frame(width: 62, height: 62)", UI)
        self.assertIn(".frame(height: 62)", UI)
        self.assertNotIn("AnyView?", UI)
        self.assertNotIn("private var tabBar", UI)
        self.assertNotIn(".glassEffect(", UI)
        self.assertNotIn('Image(systemName: "ellipsis")', UI)
        self.assertNotIn("Menu {", UI)
        self.assertNotIn('quickAction("창 관리"', UI)
        self.assertNotIn('ScarletActionRow(title: "실행 및 창 관리"', UI)
        expected = ('case home = "Home"', 'case apps = "Apps"',
                    'case sources = "Sources"', 'case settings = "Settings"')
        for case in expected:
            self.assertIn(case, UI)
        self.assertEqual(UI.count('        case home = "Home"'), 1)
        self.assertNotIn('case windowManager', UI)
        self.assertNotIn('case management', UI)
        self.assertNotIn('case manager', UI)

    def test_existing_sources_tab_and_connection_details(self):
        self.assertIn("struct ScarletSourcePresentation", UI)
        self.assertIn("public let sources: [ScarletSourcePresentation]", UI)
        self.assertIn("public let onAddSource: () -> Void", UI)
        self.assertIn("public let onOpenSource: (String) -> Void", UI)
        self.assertIn("case .sources: sourcesScreen", UI)
        self.assertIn('heading("", "소스", "")', UI)
        self.assertIn('Button(action: onAddSource)', UI)
        self.assertNotIn('case connection =', UI)
        self.assertIn("showConnectionDetails = true", UI)
        self.assertNotIn(".sheet(isPresented: $showConnectionDetails)", UI)
        self.assertIn("if showConnectionDetails {", UI)
        self.assertIn("SCARLET_CONNECTION_BACK", UI)
        self.assertIn("onAction(.serviceReadSettings)", UI)
        self.assertTrue(CONTRACT["navigation"]["connection_signing_in_settings"])

    def test_auth_presentation_does_not_claim_service_equals_login(self):
        self.assertIn("appleAuthenticated: Bool",UI)
        self.assertIn("pairingVerified: Bool",UI)
        self.assertIn("installationVerified: Bool",UI)
        self.assertIn("signingVerified: Bool",UI)
        self.assertIn("Text(verified ? \"확인됨\" : \"확인 필요\")",UI)
        self.assertIn(".disabled(!snapshot.serviceConnected)",UI)
        self.assertIn("One actor",CORE)

    def test_full_screen_structure_and_responsiveness(self):
        for case in ('case home = "Home"','case apps = "Apps"',
                     'case sources = "Sources"','case settings = "Settings"'):
            self.assertIn(case,UI)
        for required in ("ScrollView","ForEach","TextField","Button",
                         ".frame(minHeight: 44)", ".frame(maxWidth: 650, alignment: .leading)",
                         ".padding(.horizontal, 20)", "accessibilityIdentifier"):
            self.assertIn(required,UI)
        self.assertNotIn("UIScreen.main.bounds",UI)
        self.assertNotIn("UIWindow(",UI)

    def test_unverified_upstream_is_not_replaced(self):
        assert set(CONTRACT["protected_runtime"][0]) >= {"id","description"}
        self.assertNotIn("preservedGlassSwitchControl",UI)
        self.assertIn("onOpenGuest",UI)
        self.assertIn("serviceBeginSignIn",UI)
        self.assertIn("SideStore 연결 필요",UI)
        navigation=CONTRACT.get("navigation",{})
        self.assertTrue(navigation.get("bottom_tab_bar"))
        self.assertTrue(navigation.get("single_round_app_switcher"))
        self.assertEqual(navigation.get("round_switcher_size_pt"),62)
        self.assertTrue(navigation.get("bottom_tab_uses_existing_liquid_glass"))
        self.assertEqual(navigation.get("bottom_tabs"),["home","apps","sources","settings"])
        self.assertFalse(navigation.get("home_and_settings_inline"))
        self.assertTrue(navigation.get("main_screen_requires_tab"))
        self.assertFalse(navigation.get("separate_window_management_tab"))
        self.assertEqual(navigation.get("window_management_entry"),"running_guest_only")
        self.assertEqual(navigation.get("round_switcher_visibility"),"guest_scene_only")


if __name__=="__main__":
    unittest.main()
