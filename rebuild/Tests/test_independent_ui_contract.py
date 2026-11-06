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
        self.assertIn("preservedGlassSwitchControl",UI)
        self.assertIn("struct ScarletIndependentShell",UI)
        self.assertIn("struct ScarletHostPresentationSnapshot",UI)

    def test_local_settings_dont_depend_on_sidestore(self):
        a=UI.index('ScarletActionRow(title: "화면 설정"')
        b=UI.index('ScarletActionRow(title: "저장소"')
        self.assertIn("showLocalAppearance = true",UI[a:b])
        self.assertIn("onAction(.localAppearance)",UI[a:b])
        self.assertIn("onAction(.localStorageNavigation)",UI[b:b+400])
        self.assertNotIn("guard snapshot.serviceConnected",UI)

    def test_one_round_switcher_replaces_bottom_tab_bar(self):
        self.assertNotIn("private var tabBar",UI)
        self.assertNotIn("SCARLET_INDEPENDENT_TAB_BAR",UI)
        self.assertEqual(UI.count("SCARLET_SINGLE_ROUND_APP_SWITCHER"),1)
        self.assertIn(".frame(width: 62, height: 62)",UI)
        self.assertIn("preservedGlassSwitchControl: AnyView)",UI)
        self.assertIn("public let preservedGlassSwitchControl: AnyView",UI)
        self.assertIn("preservedGlassSwitchControl\n",UI)
        self.assertNotIn("AnyView?",UI)
        self.assertNotIn("Button(action: onOpenPreservedGlassWindowManager)",UI)
        self.assertNotIn('quickAction("창 관리"',UI)
        self.assertNotIn('ScarletActionRow(title: "실행 및 창 관리"',UI)
        self.assertIn("Menu {",UI)
        self.assertIn("selected = tab",UI)
        self.assertIn("accessibilityLabel(\"앱 전환 및 창 관리\")",UI)

    def test_auth_presentation_does_not_claim_service_equals_login(self):
        self.assertIn("appleAuthenticated: Bool",UI)
        self.assertIn("pairingVerified: Bool",UI)
        self.assertIn("installationVerified: Bool",UI)
        self.assertIn("signingVerified: Bool",UI)
        self.assertIn("Text(verified ? \"확인됨\" : \"확인 필요\")",UI)
        self.assertIn(".disabled(!snapshot.serviceConnected)",UI)
        self.assertIn("One actor",CORE)

    def test_full_screen_structure_and_responsiveness(self):
        for case in ('case home = "홈"','case apps = "앱"',
                     'case settings = "설정"','case connection = "연결"'):
            self.assertIn(case,UI)
        for required in ("ScrollView","ForEach","TextField","Button",
                         ".frame(minHeight: 44)", ".frame(maxWidth: 650)",
                         ".padding(.horizontal, 20)", "accessibilityIdentifier"):
            self.assertIn(required,UI)
        self.assertNotIn("UIScreen.main.bounds",UI)
        self.assertNotIn("UIWindow(",UI)

    def test_unverified_upstream_is_not_replaced(self):
        assert set(CONTRACT["protected_runtime"][0]) >= {"id","description"}
        self.assertIn("onOpenPreservedGlassWindowManager",UI)
        self.assertIn("onOpenGuest",UI)
        self.assertIn("serviceBeginSignIn",UI)
        self.assertIn("SideStore 연결 필요",UI)
        navigation=CONTRACT.get("navigation",{})
        self.assertFalse(navigation.get("bottom_tab_bar"))
        self.assertTrue(navigation.get("single_round_app_switcher"))
        self.assertEqual(navigation.get("round_switcher_size_pt"),62)
        self.assertEqual(navigation.get("page_menu_location"),"top_trailing")


if __name__=="__main__":
    unittest.main()
