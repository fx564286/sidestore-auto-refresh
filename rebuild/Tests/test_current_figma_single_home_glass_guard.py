"""Current 2026-11-08 Figma screen ownership and Liquid Glass regression guard.

This is a deterministic source contract, not proof of physical-iPhone optics.
The older six-screen measured Figma baseline is archival and may differ from
the current editable design's single Apps home + menu-open state.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "design/figma-current-screen-map.json").read_text())
NAV = json.loads((ROOT / "config/scarlet-independent-ui-contract.json").read_text())["navigation"]
UI = (ROOT / "Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
GLASS = (ROOT / "HostApp/ScarletNativeGlass.swift").read_text()
HOME = UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]
SYSTEM_TABS = UI[UI.index("    private var systemLiquidGlassTabs: some View {"):
                 UI.index("    private var legacyGlassTabs: some View {")]

class CurrentFigmaSingleHomeAndGlass(unittest.TestCase):
    def test_figma_current_screen_owner_is_not_a_second_home_tab(self):
        self.assertTrue(DESIGN["figmaFile"].endswith("QESg6S7oJS47PmlPpEX5w5"))
        self.assertEqual(DESIGN["screens"]["appsMain"], "6:75")
        self.assertEqual(DESIGN["screens"]["appsInstallMenuOpen"], "6:15")
        self.assertNotEqual(DESIGN["screens"]["appsMain"],
                            DESIGN["screens"]["appsInstallMenuOpen"])
        self.assertEqual(DESIGN["bottomTabs"], ["소스", "앱", "트윅", "설정"])
        self.assertFalse(DESIGN["independentHomeTab"])
        self.assertEqual(NAV["bottom_tab_display_labels"], DESIGN["bottomTabs"])
        self.assertEqual(NAV["apps_installer_entry_count"], 1)
        self.assertEqual(DESIGN["appsInstallTriggerCount"], 1)
        self.assertNotIn("case home =", UI)

    def test_single_plus_menu_routes_two_distinct_backends(self):
        self.assertEqual(HOME.count("                Menu {"), 1)
        self.assertEqual(HOME.count("SCARLET_INSTALLED_APPS_ADD_FILE"), 1)
        self.assertIn('Label("IPA 설치하기"', HOME)
        self.assertIn('Label("게스트 앱 설치하기"', HOME)
        self.assertIn("onAction(.serviceInstallIPA)", HOME)
        self.assertIn("onAction(.localImportGuestIPA)", HOME)
        self.assertNotIn('Button("앱 추가"', HOME)
        self.assertNotIn("showNativeAppLibrary", HOST)

    def test_ios26_uses_one_system_glass_tab_ownership_without_overlay(self):
        self.assertIn("TabView(selection: $selected)", SYSTEM_TABS)
        self.assertIn(".tabBarMinimizeBehavior(.onScrollDown)", SYSTEM_TABS)
        self.assertIn(".onAppear(perform: onSystemGlassMounted)", SYSTEM_TABS)
        self.assertNotIn("preservedGlassTabBar($selected)", SYSTEM_TABS)
        self.assertNotIn("ZStack(alignment: .bottom)", SYSTEM_TABS)
        self.assertIn("onSystemGlassMounted: {", HOST)
        self.assertIn('"system_tabbar_mounted"', HOST)
        self.assertIn('"optical_verified": "false"', HOST)
        self.assertEqual(GLASS.count("private struct SCInteractiveLiquidGlassTabs: View"), 1)
        self.assertNotIn("private struct SCInteractiveGlassTabs: View", GLASS)
        self.assertIn("GlassEffectContainer(spacing: 6)", GLASS)
        self.assertIn("UIGlassEffect(style: .clear)", GLASS)

    def test_figma_static_blur_is_not_claimed_as_runtime_proof(self):
        self.assertIn("static optical reference", DESIGN["displayGlass"])
        self.assertIn("Pending actual iPhone", DESIGN["opticalAcceptance"])
        self.assertFalse(NAV["bottom_tab_uses_existing_liquid_glass"])
        self.assertTrue(NAV["bottom_tab_uses_native_system_liquid_glass_ios26"])

if __name__ == "__main__":
    unittest.main()
