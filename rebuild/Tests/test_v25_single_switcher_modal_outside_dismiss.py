"""V25 iPhone regression: overlapping X bubble and transparent outside taps.

In V24 screenshots the separate 62pt roundTab X remained visible on top
of the native Liquid Glass switcher card. The full-scene non-key UIWindow
had point(inside:) == false outside the panel, so taps passed through to
KakaoTalk instead of closing the panel.
"""
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[1]
SRC=(R/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
LEDGER=(R/"HostApp/ScarletGuestSessionLedger.swift").read_text()

class V25ModalSwitcher(unittest.TestCase):
    def test_one_surface_only_not_a_card_plus_floating_x(self):
        root=SRC.split('    var body: some View {',1)[1].split('// UIkit pan tracks finger',1)[0]
        self.assertIn('if isOpen {',root)
        self.assertIn('} else {',root)
        self.assertIn('                    appPanel',root)
        self.assertIn('                    roundTab',root)
        self.assertIn('.transition(.identity)',root)
        self.assertLess(root.index('                    appPanel'),
                        root.index('                } else {\n                    // Persisted normalized'))
        self.assertNotIn('Image(systemName: isOpen ? "xmark"',root)

    def test_expanded_window_receives_outside_taps(self):
        body=SRC.split('final class ScarletGuestTouchPassthroughWindow: UIWindow',1)[1].split('override func point(inside point:',1)[1].split('\n}',1)[0]
        self.assertIn('guard bounds.contains(point)',body)
        self.assertIn('if isExpanded {',body)
        self.assertIn('return super.point(inside: point, with: event)',body)
        self.assertNotIn('panelRect.contains(point)',body)
        self.assertIn('return hypot(point.x - buttonCenter.x,',body)

    def test_transparent_backdrop_dismisses_without_dimming_guest(self):
        root=SRC.split('    var body: some View {',1)[1].split('// UIkit pan tracks finger',1)[0]
        self.assertIn('Color.clear',root)
        self.assertIn('.contentShape(Rectangle())',root)
        self.assertIn('.onTapGesture {',root)
        self.assertIn('panel_dismissed_outside',root)
        self.assertIn('closePanel()',root)
        self.assertNotIn('Color.black.opacity(',root)
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)',SRC)

    def test_round_button_returns_to_saved_center_immediately(self):
        close=SRC.split('    private func closePanel() {',1)[1].split('    private func switchTo',1)[0]
        self.assertIn('onPanel(false, apps.count)',close)
        self.assertIn('isOpen = false',close)
        self.assertLess(close.index('onPanel(false, apps.count)'),
                        close.index('isOpen = false'))
        self.assertIn('round_button_restored_at_saved_center',close)
        self.assertIn('.position(x: screenButtonCenter.x, y: screenButtonCenter.y)',SRC)
        self.assertIn('screenButtonCenter = initialButtonCenter',SRC)
        self.assertIn('screenButtonCenter = CGPoint(x: x, y: y)',SRC)
        self.assertIn('ScarletGuestRoundTabCenterXFractionV1',SRC)
        self.assertIn('ScarletGuestRoundTabCenterYFractionV1',SRC)
        self.assertNotIn('floating.frame =',close)

    def test_pan_disabled_in_modal_and_existing_session_policy_preserved(self):
        self.assertIn('!overlay.isExpanded else { return false }',SRC)
        self.assertIn('let recent = ScarletGuestSessionLedger.recent()',SRC)
        self.assertIn('switch_target_boot_ack',LEDGER)
        self.assertIn('switch_target_boot_mismatch',LEDGER)
        self.assertIn('SCARLET_PR48_GUEST_ROUND_TAB',SRC)
        self.assertIn('SCARLET_PR48_AIRPODS_GLASS_PANEL',SRC)

if __name__=="__main__":
    unittest.main()
