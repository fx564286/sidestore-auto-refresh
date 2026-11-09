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
                         'guard isExpanded else { return false }',
                         'let panel = CGRect(',
                         'panel.contains(point) && super.point(inside: point, with: event)',
                         'dx * dx + dy * dy <= 35 * 35',
                         'overlay.windowLevel = UIWindow.Level.alert + 1',
                         'overlay.isHidden = false'):
            self.assertIn(fragment,GUEST)

    def test_drag_saves_normalized_relative_center_not_guest_frame(self):
        for fragment in ('DragGesture(minimumDistance: 12, coordinateSpace: .global)',
                         'dockRight = onDrag(value.translation, false)',
                         'dockRight = onDrag(value.translation, true)',
                         'guard !draggingButton else { return }',
                         'positionXKey', 'positionYKey',
                         'allowedCenter(',
                         'floating_tab_position_saved',
                         'defaults?.set(Double(value.x / max(b.width, 1))',
                         'defaults?.set(Double(value.y / max(b.height, 1))',
                         'initialDockRight:',
                         'floating.frame = next',
                         'case .foregroundActive'):
            if fragment=='case .foregroundActive':continue
            self.assertIn(fragment,GUEST)
        for forbidden in ('original.frame =', 'host.frame =',
                          'root.view.frame =', 'orientationLock =',
                          'runApp(multitask: true)'):
            self.assertNotIn(forbidden,GUEST)
        self.assertIn('try await app.runApp()',HOST)

    def test_works_with_airpods_glass_and_real_guest_candidates(self):
        for fragment in ('UIGlassEffect(style: .regular)',
                         'GlassEffectContainer(spacing: 14)',
                         'switch_candidates_scanned',
                         'switch_relaunch_requested',
                         'installForGuestName', 'SCARLET_PR48_GUEST_SWITCH_TARGET'):
            self.assertIn(fragment,GUEST)

if __name__=='__main__': unittest.main()
