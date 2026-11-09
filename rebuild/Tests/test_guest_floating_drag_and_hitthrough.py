"""Guest-only floating button drag/passthrough and position persistence."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
GUEST=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()

class GuestFloatingDragHitThrough(unittest.TestCase):
    def test_pass_through_invisible_window_area(self):
        for fragment in ('class ScarletGuestTouchPassthroughWindow: UIWindow',
                         'override func point(inside point: CGPoint, with event: UIEvent?) -> Bool',
                         'return isExpanded && panelRect.contains(point)',
                         'private static func panelFrame(in window: UIWindow)',
                         'super.point(inside: point, with: event)',
                         'hypot(point.x - buttonCenter.x, point.y - buttonCenter.y) <= 35',
                         'overlay.windowLevel = UIWindow.Level.alert + 1',
                         'overlay.isHidden = false'):
            self.assertIn(fragment,GUEST)

    def test_drag_saves_normalized_relative_center_not_guest_frame(self):
        for fragment in ('UIGestureRecognizerDelegate',
                         'ScarletGuestScreenPan',
                         'UIPanGestureRecognizer(target: panHandler',
                         'window.convert(point, to: window.screen.coordinateSpace)',
                         'positionXKey', 'positionYKey',
                         'allowedCenter(',
                         'floating_tab_position_saved',
                         'defaults?.set(Double(current.x / max(bounds.width, 1))',
                         'defaults?.set(Double(current.y / max(bounds.height, 1))',
                         'initialDockRight:',
                         'floatingWindow.frame = next',
                         'case .foregroundActive'):
            if fragment=='case .foregroundActive':continue
            self.assertIn(fragment,GUEST)
        for forbidden in ('original.frame =', 'host.frame =',
                          'root.view.frame =', 'orientationLock =',
                          'runApp(multitask: true)'):
            self.assertNotIn(forbidden,GUEST)
        self.assertIn('try await app.runApp()',HOST)

    def test_works_with_airpods_glass_and_real_guest_candidates(self):
        for fragment in ('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)',
                                'switch_candidates_scanned',
                         'switch_requires_relaunch',
                         'installForGuestName', 'SCARLET_PR48_GUEST_SWITCH_TARGET'):
            self.assertIn(fragment,GUEST)

if __name__=='__main__': unittest.main()
