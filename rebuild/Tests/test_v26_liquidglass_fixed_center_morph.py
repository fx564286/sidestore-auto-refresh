"""V26: floating button's glass unfolds to a *fixed-center* switcher.

Contract: a user may drag the 62pt round tab anywhere, then tapping it
animates one native glass surface from that current absolute position to
the SAME centered card frame; clicking clear space reverses the transition
to the saved button origin. No full-scene UIWindow resize or second X bubble.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
LEDGER=(ROOT/"HostApp/ScarletGuestSessionLedger.swift").read_text()

class V26MatchedGlassGeometry(unittest.TestCase):
    def test_one_moving_glass_not_two_stacked_panels(self):
        self.assertIn("@Namespace private var glassMorphNamespace", UI)
        self.assertEqual(UI.count('matchedGeometryEffect(id: "scarlet_guest_glass_surface"'), 2)
        self.assertEqual(UI.count("in: glassMorphNamespace)"), 2)
        self.assertIn('glassPlate(radius: 28)', UI)
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: 31, showsRim: false)', UI)
        root=UI.split('    var body: some View {',1)[1].split('// UIkit pan tracks finger',1)[0]
        self.assertIn('if isOpen {',root)
        self.assertIn('} else {',root)
        self.assertIn('                    appPanel',root)
        self.assertIn('                    roundTab',root)
        self.assertNotIn('scale(scale: 0.96)',root)
        self.assertIn('.transition(.identity)',root)

    def test_panel_destination_fixed_center_regardless_of_button(self):
        self.assertIn('.position(x: geometry.size.width / 2,',UI)
        self.assertIn('y: geometry.size.height / 2)',UI)
        self.assertIn('.position(x: screenButtonCenter.x, y: screenButtonCenter.y)',UI)
        self.assertIn('screenButtonCenter = initialButtonCenter',UI)
        self.assertIn('screenButtonCenter = CGPoint(x: x, y: y)',UI)
        self.assertIn('ScarletGuestRoundTabCenterXFractionV1', UI)
        self.assertIn('ScarletGuestRoundTabCenterYFractionV1', UI)
        self.assertNotIn('floatingWindow.frame = open',UI)
        self.assertIn('window.windowScene?.coordinateSpace.bounds ?? window.bounds', UI)
        self.assertIn('floating.isExpanded = open',UI)

    def test_animation_runs_both_directions_without_bounce_or_duplicate_x(self):
        self.assertIn('Animation.spring(response: 0.45, dampingFraction: 0.88)',UI)
        self.assertIn('switcherMotion && !UIAccessibility.isReduceMotionEnabled',UI)
        self.assertIn('withAnimation(morphAnimation) { isOpen = true }',UI)
        self.assertIn('withAnimation(morphAnimation) { isOpen = false }',UI)
        self.assertIn('.animation(morphAnimation, value: isOpen)',UI)
        self.assertIn('Image(systemName: "square.stack.3d.up.fill")',UI)
        self.assertNotIn('Image(systemName: isOpen ? "xmark"',UI)
        self.assertIn('.transition(.opacity)', UI)

    def test_outside_tap_reverses_without_mask_or_guest_tap_leak(self):
        self.assertIn('Color.clear',UI)
        self.assertIn('panel_dismissed_outside',UI)
        self.assertIn('closePanel()',UI)
        self.assertIn('if isExpanded {', UI)
        self.assertIn('return super.point(inside: point, with: event)', UI)
        self.assertIn('return hypot(point.x - buttonCenter.x,', UI)
        self.assertIn('onPanel(false, apps.count)',UI)
        self.assertNotIn('Color.black.opacity(',UI)
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)',UI)

    def test_anonymous_device_logs_catch_both_animation_edges(self):
        for item in ('glass_morph_opened','glass_morph_closed'):
            self.assertIn(item,UI)
            self.assertIn(f'"{item}"',LEDGER)
        self.assertIn('button_origin_to_fixed_center',UI)
        self.assertIn('fixed_center_to_saved_button',UI)
        self.assertIn('motion": morphAnimation == nil ? "reduced" : "spring"',UI)

    def test_guest_switch_and_app_group_preserved(self):
        self.assertIn('switch_target_boot_ack',LEDGER)
        self.assertIn('switch_target_boot_mismatch',LEDGER)
        self.assertIn('private static let key = "Scarlet.Guest.ActiveSwitcherSession.V23"',LEDGER)
        self.assertIn('ScarletGuestSessionLedger.confirmSwitchHandoff(runtimeGuestID:',UI)
        self.assertIn('SCARLET_PR48_AIRPODS_GLASS_PANEL',UI)
        self.assertIn('SCARLET_PR48_GUEST_ROUND_TAB',UI)

if __name__=="__main__":
    unittest.main()
