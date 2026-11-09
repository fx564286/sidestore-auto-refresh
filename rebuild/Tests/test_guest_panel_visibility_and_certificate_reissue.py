"""V5: visible panel content, stable screen-space drag and cert fallback."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
SIGN = (ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
HOST = (ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()

class V5Contracts(unittest.TestCase):
    def test_panel_content_above_native_glass(self):
        for fragment in ("ZStack(alignment: .topLeading)",
                         "glassPlate(radius: 28)", ".zIndex(2)",
                         "switch_panel_content_rendered",
                         "UIView.performWithoutAnimation",
                         "switch_panel_geometry_applied",
                         "width = open ? min(410",
                         "GlassEffectContainer(spacing: 14)"):
            self.assertIn(fragment, UI)
        self.assertNotIn('glassEffectID("guest-expanded"', UI)
        self.assertNotIn(".glassEffectTransition(.matchedGeometry)", UI)

    def test_pan_stays_in_screen_coordinates(self):
        for fragment in ("ScarletGuestScreenPan", "UIGestureRecognizerDelegate",
                         "window.convert(point, to: window.screen.coordinateSpace)",
                         "dragStartScreen = screenPoint",
                         "initial.x + screenPoint.x - touch.x",
                         "ScarletGuestFloatingDockChanged"):
            self.assertIn(fragment, UI)
        self.assertNotIn('DragGesture(minimumDistance: 12, coordinateSpace: .global)', UI)
        self.assertIn("try await app.runApp()", HOST)

    def test_certificate_reissue_requires_consent_and_rollback(self):
        for fragment in ("SideInstaller 새 P12 발급·내보내기",
                         "isConfirmingCertReplacement = true",
                         "importExportedP12(replaceExisting: true)",
                         "existingCert", "existingPassword", "existingDate",
                         "replacement_readback_failed", "provider_fallback_available",
                         "sideinstaller_p12_stored"):
            self.assertIn(fragment, SIGN)
        self.assertNotIn("if !readiness.liveContainerCertificatePresent", SIGN)

if __name__ == "__main__":
    unittest.main()
