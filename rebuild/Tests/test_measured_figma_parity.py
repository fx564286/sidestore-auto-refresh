"""Historical Figma six-screen measurements versus the user's later three-tab override.

The immutable 4-tab Figma baseline is archival, NOT a claim that current
runtime still has four tabs. Actual iPhone pixel parity remains unverified.
"""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DESIGN=json.loads((ROOT/"design/figma-measured-baseline.json").read_text())
CURRENT=json.loads((ROOT/"config/scarlet-independent-ui-contract.json").read_text())
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
HOME=UI[UI.index("    private var home: some View {"):UI.index("    private func installPathRow(")]

class FigmaMeasuredParity(unittest.TestCase):
    def test_six_original_screen_nodes_remain_as_design_archive(self):
        screens=DESIGN["screens"]
        self.assertEqual(len(screens),6)
        self.assertEqual(len({s["figmaNodeId"] for s in screens}),6)
        self.assertEqual(DESIGN["design"]["viewport"],{"w":390,"h":844})
        self.assertEqual(DESIGN["design"]["bottomBar"]["labels"],
                         ["Home","Apps","Sources","Settings"])
        self.assertEqual(DESIGN["design"]["bottomBar"]["tabCount"],4)

    def test_user_override_replaces_old_apps_tab_without_touching_glass(self):
        self.assertEqual(CURRENT["navigation"]["bottom_tabs"],
                         ["home","sources","settings"])
        self.assertEqual(CURRENT["navigation"]["bottom_tab_display_labels"],
                         ["Home","Sources","Settings"])
        self.assertIn("preservedGlassTabBar($selected)",UI)
        self.assertNotIn('case apps = "Apps"',UI)
        self.assertNotIn(".glassEffect(",UI)
        self.assertNotIn("case windowManager",UI)
        self.assertIn('case .home: "square.grid.2x2"',UI)
        self.assertEqual(DESIGN["design"]["roundSwitcher"]["w"],62)

    def test_merged_home_labels_filters_and_actions_are_real(self):
        self.assertIn('heading("", "설치된 앱", "")',HOME)
        self.assertIn('TextField("설치된 앱 검색"',HOME)
        self.assertIn('installPathRow("SideStore 앱 설치"',HOME)
        self.assertIn('installPathRow("게스트 앱 설치"',HOME)
        self.assertIn("guests: visibleGuests",HOME)
        self.assertIn("searchText.isEmpty ||",UI)
        self.assertNotIn('Text("Madeira")',UI)
        self.assertNotIn('private var apps: some View {',UI)

    def test_settings_native_tab_keeps_original_engine_form(self):
        self.assertIn("if selected == .settings {",UI)
        self.assertIn("SCARLET_INLINE_NATIVE_LC_SETTINGS",UI)
        self.assertIn("LCSettingsView()",HOST)
        self.assertNotIn(".sheet(isPresented: $showNativeSettings)",HOST)
        self.assertNotIn("if showConnectionDetails {",UI)

    def test_not_false_physical_device_certification(self):
        self.assertTrue(DESIGN["runtimeGates"]["realIPhoneScreenshots"])
        self.assertTrue(DESIGN["runtimeGates"]["nativeGlassInteractive"])
        self.assertIn("not proof"," ".join(DESIGN["limitations"]).lower())

if __name__=="__main__":
    unittest.main()
