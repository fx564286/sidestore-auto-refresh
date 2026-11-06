"""Tests real iOS 26+ glass material and tab interaction, not screenshots.

Physical-device optical effect still requires iPhone evidence and dynamic test.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
GLASS=(ROOT/"HostApp/ScarletNativeGlass.swift").read_text()
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
TABS=GLASS[GLASS.index("private struct SCInteractiveGlassTabs"):GLASS.index("struct ScarletNativeGlassSwitcher")]

class NativeLiquidGlassContract(unittest.TestCase):
    def test_ios26_uses_swiftui_real_glass_compositor(self):
        self.assertIn("GlassEffectContainer(spacing:",TABS)
        self.assertIn(".glassEffect(.regular, in: Capsule())",TABS)
        self.assertIn(".regular.tint(.white.opacity(0.12)).interactive()",TABS)
        self.assertIn('.glassEffectID("scarlet-active-tab", in: activeGlassNamespace)',TABS)
        self.assertIn("SCARLET_REAL_GLASS_TAB_BAR",TABS)
        self.assertIn("SCInteractiveGlassTabs(selected: $selected)",TABS)

    def test_previous_flat_gray_selected_fill_not_used_on_ios26(self):
        modern=TABS[:TABS.index("@available(iOS 16.0, *)")]
        self.assertNotIn(".background(selected == tab ? Color.white.opacity(0.16)",modern)
        self.assertNotIn("UIBlurEffect(",modern)
        self.assertNotIn(".clipShape(Capsule())",modern)
        self.assertIn("withAnimation(.spring(",modern)
        self.assertIn(".contentShape(Capsule())",modern)

    def test_old_os_and_accessibility_fallback_is_explicit(self):
        self.assertIn("if #available(iOS 26.0, *)",TABS)
        self.assertIn("!UIAccessibility.isReduceTransparencyEnabled",TABS)
        self.assertIn("SCNativeLiquidGlassSurface(cornerRadius: 31",TABS)

    def test_original_dimensions_and_no_fake_shell_glass(self):
        self.assertIn(".frame(height: 62)",TABS)
        self.assertIn(".padding(.horizontal, 19)",UI)
        self.assertIn("preservedGlassTabBar($selected)",UI)
        self.assertNotIn(".glassEffect(",UI)
        self.assertIn("ScarletNativeGlassTabBar(selected: tab)",HOST)
        for tab in ('case sources = "소스"','case apps = "앱"',
                    'case tweaks = "트윅"','case settings = "설정"'):
            self.assertIn(tab,UI)

if __name__=="__main__":
    unittest.main()
