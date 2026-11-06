"""Retain Figma settings reference, but enforce native inline settings routing.

User's latest verified behavior overrides the old Figma mock navigation.
"""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
G=json.loads((ROOT/"reports/figma-alignment-audit-20261106.json").read_text())["geometry"]
CONFIG=json.loads((ROOT/"config/scarlet-independent-ui-contract.json").read_text())["navigation"]

class SettingsParity(unittest.TestCase):
    def test_original_measured_card_axes_are_preserved_as_reference(self):
        self.assertEqual(G["settingsContentLeftPt"],20)
        self.assertEqual(G["settingsCardWidthsPt"],[350,350,350])
        self.assertEqual(G["settingsPrimaryActionCenterXPt"],195)
        self.assertEqual(G["settingsCardCount"],3)

    def test_original_livecontainer_settings_is_direct_tab_content(self):
        self.assertIn("if selected == .settings {",UI)
        self.assertIn("nativeSettings()",UI)
        self.assertIn("nativeSettings: {",HOST)
        self.assertIn("LCSettingsView()",HOST)
        self.assertNotIn(".sheet(isPresented: $showNativeSettings)",HOST)
        self.assertTrue(CONFIG["settings_tab_inline_native"])

    def test_no_different_labels_open_same_settings_sheet(self):
        for x in ('ScarletActionRow(title: "화면 설정"',
                  'ScarletActionRow(title: "저장소"',
                  'ScarletActionRow(title: "진단 로그"'):
            self.assertNotIn(x,UI)
        INTEGRATOR=(ROOT/"integration/apply_scarlet_host.py").read_text()
        self.assertIn("SCARLET_SETTINGS_NATIVE_APPLE_LOGIN",INTEGRATOR)
        self.assertIn("SCARLET_NATIVE_DIAGNOSTICS_ENTRY",INTEGRATOR)
        self.assertNotIn('Text("설정")',UI)
        self.assertNotIn("showConnectionDetails",UI)

    def test_actual_iphone_screen_and_auth_remain_separate_gates(self):
        self.assertTrue(CONFIG["signin_request_requires_verified_engine"])
        self.assertIn("showScarletAppleIDLogin = true",HOST)

if __name__=="__main__":
    unittest.main()
