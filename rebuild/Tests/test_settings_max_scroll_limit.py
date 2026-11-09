"""Regression: scrolling to the end of native Settings must not over-travel.

2026-11-09 reference images: first is intended maximum-scroll position;
second shows ~140pt extra scrolling and a blank area below the version row.
This asserts the cause is removed without changing original LC settings
labels or the iOS 26 Liquid Glass tabbar collapse-on-scroll behavior.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
GLASS=(ROOT/"HostApp/ScarletNativeGlass.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()

class SettingsMaxScrollRegression(unittest.TestCase):
    def test_native_settings_does_not_stack_clearance_on_system_tabbar(self):
        self.assertIn('func scarletSettingsScrollLimit() -> some View',GLASS)
        part=GLASS.split('func scarletSettingsScrollLimit() -> some View {',1)[1].split(
            '// The nested JIT-Less diagnostics',1)[0]
        self.assertIn('if #available(iOS 26.0, *) {\n            self',part)
        self.assertNotIn('height: 140',part)
        self.assertNotIn('.contentMargins(.bottom, 140',part)
        self.assertIn('height: 72',part)

    def test_original_settings_form_uses_new_limit_without_changing_controls(self):
        form=PATCH.split('form_style_anchor =',1)[1].split(
            '# The original LC settings action',1)[0]
        self.assertIn('scarletSettingsScrollLimit()',form)
        self.assertNotIn('scarletDockScrollClearance()',form)
        self.assertIn('scarletNativeListTheme()',form)
        self.assertIn('lc.tabView.settings',form)

    def test_native_glass_tabbar_still_owns_system_safe_area(self):
        self.assertIn('.tabBarMinimizeBehavior(.onScrollDown)',UI)
        self.assertIn('nativeSettings()',UI)
        self.assertIn('SCARLET_INLINE_NATIVE_LC_SETTINGS',UI)
        self.assertNotIn('.safeAreaInset(edge: .bottom',UI)

    def test_other_native_lists_keep_their_separate_clearance_contract(self):
        self.assertIn('func scarletDockScrollClearance() -> some View',GLASS)
        self.assertIn('func scarletDiagnosticScrollMargins() -> some View',GLASS)
        tweak=PATCH.split('def apply_scarlet_native_tweaks_theme(',1)[1].split(
            'def attach_jitless_diagnostic_scroll_margins(',1)[0]
        self.assertIn('scarletDockScrollClearance()',tweak)

if __name__=="__main__":
    unittest.main()
