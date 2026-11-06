"""Figma parity contract based on actual inspected Figma node IDs and labels.

This is not a screenshot pixel-diff or proof of native Liquid Glass.
It guards against accidental loss of editable Figma structure in SwiftUI.
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = json.loads((ROOT / "design/figma-measured-baseline.json").read_text())
UI = (ROOT / "Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()

class FigmaMeasuredParity(unittest.TestCase):
    def test_six_unique_measured_screens(self):
        screens = DESIGN["screens"]
        self.assertEqual(len(screens), 6)
        self.assertEqual(len({s["figmaNodeId"] for s in screens}), 6)
        self.assertEqual(DESIGN["design"]["viewport"], {"w": 390, "h": 844})
        for s in screens:
            segments = s["figmaNodeId"].split(":")
            self.assertEqual(len(segments), 2)
            self.assertTrue(all(part.isdecimal() for part in segments))
            self.assertTrue(s["requiredCopy"])

    def test_navigation_and_glass_boundaries(self):
        nav = DESIGN["design"]["bottomBar"]
        self.assertEqual(nav["labels"], ["Home", "Apps", "Sources", "Settings"])
        self.assertEqual([nav["w"], nav["h"], nav["tabCount"]], [352, 62, 4])
        self.assertEqual(DESIGN["design"]["roundSwitcher"]["w"], 62)
        self.assertIn("preservedGlassTabBar($selected)", UI)
        self.assertNotIn("preservedGlassSwitchControl", UI)
        for tab in nav["labels"]:
            self.assertIn('= "' + tab + '"', UI)
        self.assertNotIn(".glassEffect(", UI)
        self.assertNotIn("case windowManager", UI)
        self.assertIn('case .apps: "square.grid.3x3"', UI)
        self.assertIn('case .sources: "books.vertical"', UI)
        axis = DESIGN["design"]["alignment"]
        self.assertEqual(axis["guestSegmentWidthPt"], axis["guestRowWidthPt"])
        self.assertTrue(axis["homeAndSettings"]["settingsInline"])
        self.assertTrue(axis["homeAndSettings"]["hideBottomTabsOnHome"])
        self.assertEqual(axis["homeAndSettings"]["engineEntryHeightsPt"], [78,78])
        self.assertNotIn('Text(guest.isRunning ? "전환" : "실행")', UI)


    def test_screen_copy_retained_in_swiftui(self):
        for screen in DESIGN["screens"]:
            if screen["codeSection"] is None:
                continue
            with self.subTest(screen=screen["id"]):
                self.assertIn(screen["codeSection"], UI)
                for label in screen["requiredCopy"]:
                    self.assertIn(label, UI)

    def test_app_screen_native_import_search_no_recent_filters(self):
        apps=UI[UI.index("    private var apps: some View {"):UI.index("    private var sourcesScreen:")]
        self.assertIn('heading("", "가상 앱", "")',apps)
        self.assertIn('TextField("앱 검색"',apps)
        self.assertIn('onAction(.localImportGuestIPA)',apps)
        self.assertIn('SCARLET_NATIVE_GUEST_IMPORT',apps)
        self.assertNotIn('SCARLET_APP_FILTER_',UI)
        self.assertNotIn('private enum AppFilter:',UI)
        self.assertIn('searchText.isEmpty ||',UI)
        self.assertNotIn('Text("Madeira")',UI)

    def test_account_detail_keeps_bottom_tabs(self):
        self.assertIn("if showConnectionDetails {", UI)
        self.assertNotIn(".sheet(isPresented: $showConnectionDetails)", UI)
        self.assertIn("SCARLET_CONNECTION_BACK", UI)

    def test_not_a_false_physical_device_certification(self):
        self.assertTrue(DESIGN["runtimeGates"]["realIPhoneScreenshots"])
        self.assertTrue(DESIGN["runtimeGates"]["nativeGlassInteractive"])
        self.assertIn("not proof", " ".join(DESIGN["limitations"]).lower())
        self.assertIsNone(next(s for s in DESIGN["screens"] if s["id"] == "overlay")["codeSection"])

if __name__ == "__main__":
    unittest.main()
