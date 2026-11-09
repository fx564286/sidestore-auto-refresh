"""Native Liquid Glass implementation contract for iOS 26+.

Static evidence verifies proper Apple Glass APIs and actual interaction
paths. Only physical iPhone testing can establish optical/gesture parity.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
GLASS=(ROOT/"HostApp/ScarletNativeGlass.swift").read_text()
GUEST=(ROOT/"HostApp/ScarletGuestSwitcherOverlay.swift").read_text()
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
TABS=GLASS[GLASS.index("private struct SCInteractiveLiquidGlassTabs"):
           GLASS.index("@available(iOS 16.0, *)\nstruct ScarletNativeGlassTabBar")]

class NativeLiquidGlassContract(unittest.TestCase):
    def test_ios26_uses_apple_owned_system_tabbar_not_manual_overlay(self):
        # Apple's system tab bar owns its Liquid Glass rendering and
        # navigational scroll safe areas, including pushed JIT-Less Forms.
        self.assertIn("systemLiquidGlassTabs", UI)
        self.assertIn("TabView(selection: $selected) {", UI)
        self.assertIn("ForEach(Tab.allCases, id: \\.self)", UI)
        self.assertIn("Label(tab.rawValue, systemImage: tab.icon)", UI)
        self.assertIn(".tabBarMinimizeBehavior(.onScrollDown)", UI)
        self.assertIn("SCARLET_IOS26_NATIVE_SYSTEM_GLASS_TABS", UI)
        # The old custom bar only exists inside the legacy branch.
        self.assertIn("private var legacyGlassTabs: some View", UI)
        self.assertIn("preservedGlassTabBar($selected)", UI)
        source = UI[UI.index("private var systemLiquidGlassTabs: some View"):
                    UI.index("private var legacyGlassTabs: some View")]
        self.assertNotIn("preservedGlassTabBar($selected)", source)
        self.assertNotIn("ZStack(alignment: .bottom)", source)

    def test_ios26_uses_system_glass_compositor_and_real_selected_material(self):
        self.assertIn("GlassEffectContainer(spacing: 6)",TABS)
        self.assertIn(".glassEffect(.regular.interactive(), in: .capsule)",TABS)
        self.assertIn(".regular.tint(Color(red: 170.0/255,",TABS)
        self.assertIn('.glassEffectID("selected-tab", in: selectionNamespace)',TABS)
        self.assertNotIn('.matchedGeometryEffect(id: "selection", in: selectionNamespace)',TABS)
        # The backplate has its own genuine OS glass layer; it must not
        # merge inside the moving selection's GlassEffectContainer at rest.
        self.assertIn(".frame(height: 62)\n        // A separate system-glass backplate",TABS)
        self.assertIn(".background {\n            Capsule()\n                .glassEffect(.regular.interactive(), in: .capsule)",TABS)
        self.assertIn("SCInteractiveLiquidGlassTabs(selected: $selected)",GLASS)
        self.assertIn("SCARLET_LIVE_GLASS_BAR_MATERIAL",TABS)
        self.assertIn('fields: ["api": "SwiftUI.GlassEffectContainer"',TABS)

    def test_selected_segment_morphs_on_tap_and_drag(self):
        self.assertIn("withAnimation(.spring(",TABS)
        self.assertIn("DragGesture(minimumDistance: 8)",TABS)
        self.assertIn(".simultaneousGesture(",TABS)
        self.assertIn("select(tabs[index])",TABS)
        self.assertIn("select(tab)",TABS)
        self.assertIn(".contentShape(Capsule())",TABS)

    def test_no_flat_painted_selection_in_ios26_glass_path(self):
        self.assertNotIn(".background(selected == tab ?",TABS)
        self.assertNotIn("UIBlurEffect(",TABS)
        self.assertNotIn(".clipShape(Capsule())",TABS)
        self.assertNotIn("SCNativeLiquidGlassSurface",TABS)
        self.assertNotIn("Color.black.opacity(",TABS)

    def test_fallback_for_old_os_and_reduce_transparency_remains_separate(self):
        self.assertIn("if #available(iOS 26.0, *)",GLASS)
        self.assertIn("!UIAccessibility.isReduceTransparencyEnabled",GLASS)
        self.assertIn("SCNativeLiquidGlassSurface(cornerRadius: 31)",GLASS)

    def test_guest_switcher_and_panel_use_native_glass(self):
        self.assertIn("SCARLET_LIVE_GLASS_SWITCHER_MATERIAL",GLASS)
        self.assertIn(".glassEffect(.regular.interactive(), in: .circle)",GLASS)
        self.assertIn("SCARLET_GUEST_PANEL_NATIVE_GLASS_MATERIAL",GUEST)
        self.assertIn(".glassEffect(.regular, in: .rect(cornerRadius: 24))",GUEST)
        self.assertIn(".glassEffect(.regular.tint(.purple.opacity(0.28)).interactive(),",GUEST)
        self.assertIn("SCARLET_GUEST_EXIT_TO_SCARLET",GUEST)
        self.assertIn("SCARLET_GUEST_ONLY_ROUND_SWITCHER",GUEST)

    def test_existing_geometry_and_four_tab_destinations(self):
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
