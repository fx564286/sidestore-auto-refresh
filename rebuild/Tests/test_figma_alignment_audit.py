"""Validate measured editable Figma centerlines against SwiftUI host adapters.

This is geometric source-level parity, NOT an actual iPhone screenshot test.
"""
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
AUDIT=json.loads((ROOT/"reports/figma-alignment-audit-20261106.json").read_text())
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()

class AlignmentTests(unittest.TestCase):
    def test_all_six_screens_have_centered_native_tab_bar(self):
        g=AUDIT["geometry"]
        self.assertEqual(len(AUDIT["screens"]),6)
        self.assertEqual(g["bottomBarCenterX"],g["viewportCenterX"])
        self.assertEqual(g["tabWidthsPt"],[81]*4)
        self.assertEqual(g["iconLabelCenterOffsetPt"],[0]*4)
        self.assertEqual(g["bottomBarX"],19)
        self.assertEqual(g["bottomBarWidth"],352)

    def test_window_manager_uses_equal_segments_and_action_buttons(self):
        g=AUDIT["geometry"]
        self.assertEqual(g["glassOverlaySegmentWidthPt"],153)
        self.assertEqual(g["glassOverlaySegmentXPt"],[7,162])
        self.assertEqual(g["windowActionWidthsPt"],[102]*3)
        self.assertFalse(AUDIT["policy"]["doNotDuplicateSwitchers"] is False)

    def test_home_settings_same_screen_without_tab(self):
        home=UI[UI.index("    private var home: some View {"):UI.index("    private var visibleGuests:")]
        self.assertEqual(home.count('engineEntry("'),2)
        self.assertIn('heading("", "설정", "")',home)
        self.assertIn('if selected != .home {',UI)
        self.assertNotIn('SCARLET_CENTERED_WORKSPACE_STATS',UI)
        self.assertNotIn('quickAction("앱 추가"',UI)
        self.assertIn('preservedGlassTabBar($selected)',UI)
        self.assertEqual(AUDIT["geometry"]["homeEngineEntryWidthsPt"],[350,350])


if __name__=="__main__":
    unittest.main()
