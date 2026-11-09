"""V9: no stacked UIKit rims, shadows or whole-overlay compositor."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
GLASS=(ROOT/'HostApp/ScarletNativeGlass.swift').read_text()
GUEST=(ROOT/'HostApp/ScarletFullscreenGuestTab.swift').read_text()
MAIN=(ROOT/'HostApp/ScarletNativeGlass.swift').read_text()
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()

class V9SingleSurface(unittest.TestCase):
    def test_main_tab_default_rim_unchanged(self):
        self.assertIn('var showsRim: Bool = true',GLASS)
        self.assertIn('if #available(iOS 26.0, *), showsRim {',GLASS)
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: 31)',MAIN)
        self.assertIn('let glass = UIGlassEffect(style: .clear)',GLASS)
    def test_guest_has_one_contrast_border_only(self):
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)',GUEST)
        self.assertIn('SCNativeLiquidGlassSurface(cornerRadius: 31, showsRim: false)',GUEST)
        self.assertIn('.strokeBorder(Color.primary.opacity(0.24), lineWidth: 0.75)',GUEST)
        self.assertIn('.strokeBorder(Color.primary.opacity(0.28), lineWidth: 0.8)',GUEST)
        self.assertNotIn('GlassEffectContainer(spacing: 14)',GUEST)
        self.assertNotIn('.shadow(color: .black.opacity(0.19)',GUEST)
        self.assertNotIn('.strokeBorder(.white.opacity(0.58)',GUEST)
    def test_overlay_and_host_geometry_preserved(self):
        for x in ('ScarletGuestTouchPassthroughWindow','overlay.layer.masksToBounds = true',
                  'width = open ? min(430','height = open ? min(cardHeight + 84',
                  'case .changed:', 'settleOverlayAfterRotation()'):
            self.assertIn(x,GUEST)
        self.assertIn('try await app.runApp()',HOST)
        self.assertNotIn('original.frame =',GUEST)
        self.assertNotIn('host.frame =',GUEST)
if __name__=='__main__': unittest.main()
