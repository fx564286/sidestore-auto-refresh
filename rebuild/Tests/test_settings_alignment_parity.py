"""Figma (6:136) settings alignment and service parity acceptance contract."""
from pathlib import Path
import json
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
G=json.loads((ROOT/"reports/figma-alignment-audit-20261106.json").read_text())["geometry"]
D=json.loads((ROOT/"design/figma-measured-baseline.json").read_text())
A=UI[UI.index("    private var settings: some View {"):UI.index("    private var connection: some View {")]
B=UI[UI.index("    private var connection: some View {"):]

class SettingsParity(unittest.TestCase):
    def test_measured_card_axes(self):
        self.assertEqual(G["settingsContentLeftPt"],20)
        self.assertEqual(G["settingsCardWidthsPt"],[350,350,350])
        self.assertEqual(G["settingsCardHeightsPt"],[165,129,80])
        self.assertEqual(G["settingsIconInsetPt"],G["settingsCardHeadingInsetPt"])
        self.assertEqual(G["settingsRowTextInsetPt"]-G["settingsIconInsetPt"],48)
        self.assertEqual(G["settingsPrimaryActionCenterXPt"],195)
        self.assertEqual(G["settingsCardCount"],3)

    def test_exactly_three_aligned_panels(self):
        self.assertEqual(A.count("compactSettingsCard {"),2)
        self.assertEqual(A.count("ScarletActionRow(title:"),3)
        self.assertNotIn("ScarletPanel {",A)
        self.assertIn('Text("컨테이너")',A)
        self.assertIn('heading("", "설정", "")',A)
        self.assertNotIn("앱 데이터 및 백업",A)
        self.assertNotIn("오류 및 동작 기록",A)
        self.assertIn(".multilineTextAlignment(.center)",A)
        self.assertIn(".padding(.horizontal, 8)",A)
        self.assertIn(".frame(height: 62)",A)

    def test_original_sidestore_controls_not_removed(self):
        for text in ('ScarletActionRow(title: "SideStore 열기"', 
                     'Text("자동 갱신")','onAction(.serviceRefreshApp)',
                     'onAction(.localOpenEmbeddedSideStore)',
                     'onAction(.serviceBeginSignIn)'):
            self.assertIn(text,B)
        self.assertNotIn('ScarletActionRow(title: "SideStore 열기"',A)
        self.assertNotIn('Text("자동 갱신")',A)

    def test_essential_text_and_device_gate(self):
        settings=next(x for x in D["screens"] if x["id"]=="settings")
        self.assertNotIn("앱 데이터 및 백업",settings["requiredCopy"])
        self.assertTrue(D["runtimeGates"]["realIPhoneScreenshots"])

if __name__=="__main__":
    unittest.main()
