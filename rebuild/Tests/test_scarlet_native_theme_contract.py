"""Regression tests for Figma parity without replacing native LC controls."""
import importlib.util
from pathlib import Path
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
GLASS = (ROOT / "HostApp/ScarletNativeGlass.swift").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
INTEGRATOR = ROOT / "integration/apply_scarlet_host.py"
spec = importlib.util.spec_from_file_location("scarlet_integrator", INTEGRATOR)
integrator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integrator)


class NativeScarletTheme(unittest.TestCase):
    def test_glass_floats_over_content_not_in_separate_footer(self):
        shell = UI[UI.index("public struct ScarletIndependentShell: View"):]
        self.assertIn("ZStack(alignment: .bottom)", shell)
        self.assertIn("preservedGlassTabBar($selected)", shell)
        self.assertEqual(shell.count("preservedGlassTabBar($selected)"), 1)
        self.assertIn("SCARLET_SCROLL_END_CLEARANCE", shell)
        self.assertIn(".frame(height: 140)", shell)
        self.assertIn(".scarletIndependentScrollEdge()", shell)
        self.assertNotIn(".padding(.bottom, 106)", shell)
        self.assertNotIn("Color.clear.frame(height: 82)", shell)
        self.assertIn(".padding(.horizontal, 19)", shell)
        self.assertIn("SCARLET_NATIVE_GLASS_BOTTOM_TAB_BAR", shell)

    def test_jitless_child_forms_have_real_scroll_content_margins(self):
        self.assertIn("scarletDiagnosticScrollMargins()", INTEGRATOR.read_text())
        self.assertIn(".contentMargins(.bottom, 84, for: .scrollContent)", GLASS)
        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path
            engine = Path(tmp)
            target = engine/"LiveContainerSwiftUI/Views/Settings/LCJITLessDiagnoseView.swift"
            target.parent.mkdir(parents=True)
            source = (
                'Form {\n    Text("Entitlements remain original")\n'
                '            }\n'
                '            .navigationTitle(isLiveProcess ? "LiveProcess Entitlements" : "LiveContainer Entitlements")\n'
                'Form {\n    Button("Test JIT-Less") {}\n'
                '            }\n'
                '            .navigationTitle("lc.settings.jitlessDiagnose".loc)\n'
            )
            target.write_text(source)
            report = integrator.attach_jitless_diagnostic_scroll_margins(engine)
            compiled = target.read_text()
            self.assertEqual(report["originalNestedForms"], 2)
            self.assertEqual(compiled.count(".scarletDiagnosticScrollMargins()"), 2)
            self.assertIn('Button("Test JIT-Less")', compiled)
            self.assertIn('Entitlements remain original', compiled)

    def test_real_tweaks_settings_are_not_replaced_by_fake_card_actions(self):
        for item in ("nativeSettings()", "nativeTweaks()"):
            self.assertIn(item, UI)
        self.assertIn("LCSettingsView()", HOST)
        self.assertIn("LCTweaksView()", HOST)
        self.assertIn("theme_native_settings_section_rows", INTEGRATOR.read_text())
        self.assertIn("apply_scarlet_native_tweaks_theme", INTEGRATOR.read_text())

    def test_form_and_list_inset_is_applied_to_native_scrollers(self):
        patch = INTEGRATOR.read_text()
        self.assertIn("scarletDockScrollClearance()", patch)
        self.assertIn(".safeAreaInset(edge: .bottom, spacing: 0)", GLASS)
        self.assertIn(".scrollEdgeEffectHidden(true, for: .all)", GLASS)
        self.assertIn("Color.clear.frame(height: 140)", GLASS)
        self.assertNotIn("Color.clear.frame(height: 82)", patch)

    def test_theme_uses_exact_figma_surface_and_native_glass(self):
        self.assertIn("36.0/255, green: 35.0/255, blue: 58.0/255", UI)
        self.assertIn("69.0/255, green: 66.0/255, blue: 93.0/255", UI)
        self.assertIn(".glassEffect(.regular.interactive(), in: .capsule)", GLASS)
        self.assertIn("lineWidth: 1.2", GLASS)
        self.assertNotIn("SCNativeLiquidGlassSurface(cornerRadius: 31)\n                .overlay", GLASS)

    def test_each_upstream_settings_section_receives_a_card_background(self):
        # A pinned 15-section LC Form plus the Scarlet diagnostics Section.
        chunks = []
        for index in range(16):
            indent = " " * (20 if index % 3 == 0 else 16)
            chunks.extend([
                f"{indent}Section {{\n",
                f'{indent}    Text("ACTION_{index}")\n',
                f"{indent}}} header: {{\n",
                f'{indent}    Text("HEADER_{index}")\n',
                f"{indent}}} footer: {{\n",
                f'{indent}    Text("FOOTER_{index}")\n',
                f"{indent}}}\n",
            ])
        src = "".join(chunks)
        result, count = integrator.theme_native_settings_section_rows(src)
        self.assertEqual(count, 16)
        self.assertEqual(result.count(".listRowBackground("), 16)
        for index in range(16):
            self.assertIn(f'ACTION_{index}', result)
            self.assertIn(f'FOOTER_{index}', result)
        with self.assertRaises(AssertionError):
            integrator.theme_native_settings_section_rows(src[:-1].replace("Section {", "MissingSection {", 1))


if __name__ == "__main__":
    unittest.main()
