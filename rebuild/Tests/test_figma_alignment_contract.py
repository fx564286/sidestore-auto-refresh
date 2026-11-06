"""Visual contract: the six measured Figma screens have centered interactive slots.

A screenshot preview is not proof of native Liquid Glass at runtime; that
remains separately gated by the original host renderer and iPhone test.
"""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
G=json.loads((ROOT/"reports/figma-alignment-audit-20261106.json").read_text())
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()

class FigmaGeometryContract(unittest.TestCase):
    def test_all_six_screens_have_matching_geometry(self):
        self.assertEqual(len(G["screens"]),6)
        m=G["geometry"]
        self.assertEqual(m["viewportWidthPt"],390)
        self.assertEqual(m["bottomBarCenterX"],m["viewportCenterX"])
        self.assertEqual(sum(m["tabWidthsPt"]),324)
        self.assertEqual(m["tabWidthsPt"],[81]*4)
        self.assertEqual(m["iconLabelCenterOffsetPt"],[0]*4)
        self.assertEqual(m["bottomBarHeight"],62)

    def test_round_switcher_and_two_equal_window_segments(self):
        g=G["geometry"]
        self.assertEqual(g["roundSwitcherDiameterPt"],62)
        self.assertEqual(g["glassOverlaySegmentWidthPt"],153)
        self.assertEqual(g["glassOverlaySegmentXPt"],[7,162])
        self.assertEqual(g["windowActionWidthsPt"],[102,102,102])
        self.assertTrue(G["policy"]["preserveOriginalLiquidGlass"])
        self.assertTrue(G["policy"]["doNotBuildFauxGlass"])
        self.assertTrue(G["policy"]["noSeparateWindowManagerTab"])

    def test_home_rolls_back_inline_settings_only(self):
        home=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]
        self.assertEqual(home.count('installPathRow("'),2)
        self.assertIn('installPathRow("iOS 앱 설치"',home)
        self.assertIn('installPathRow("게스트 앱 설치"',home)
        self.assertNotIn('heading("", "설정", "")',home)
        self.assertNotIn('ScarletActionRow(title: "LiveContainer 전체 설정"',home)
        self.assertNotIn('sectionTitle("최근 앱")',home)
        self.assertNotIn('sectionTitle("빠른 작업")',home)
        self.assertNotIn('if selected != .home {',UI)

    def test_native_glass_control_must_be_injected_not_recreated(self):
        self.assertIn("preservedGlassTabBar: (Binding<Tab>) -> AnyView",UI)
        self.assertIn("preservedGlassTabBar($selected)",UI)
        self.assertNotIn("preservedGlassSwitchControl",UI)
        self.assertNotIn(".glassEffect(",UI)
        self.assertNotIn("private var tabBar",UI)

if __name__=="__main__":
    unittest.main()
