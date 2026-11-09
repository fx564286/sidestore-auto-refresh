"""V7 optical/scene safety, orientation diagnostics, one JIT-less owner and provenance."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
PATCH=(ROOT/"integration/apply_scarlet_host.py").read_text()
PANEL=(ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
WORKER=(ROOT/"integration/ScarletGuestCertificateAgent.swift.txt").read_text()
TRANSPORT=(ROOT/"HostApp/ScarletCertificateXPCSupport.swift").read_text()
RECORDER=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()

class V7SafetyContracts(unittest.TestCase):
    def test_rim_inside_one_clipped_glass_card(self):
        self.assertIn("SCNativeLiquidGlassSurface(cornerRadius: radius)", UI)
        self.assertIn(".strokeBorder(Color.primary.opacity(0.22), lineWidth: 0.9)",UI)
        self.assertIn(".padding(.horizontal, 12)",UI)
        self.assertLess(UI.index(".clipShape(RoundedRectangle(cornerRadius: 28"),
                        UI.index(".strokeBorder(Color.primary.opacity(0.22)"))
        self.assertLess(UI.index(".strokeBorder(Color.primary.opacity(0.22)"),
                        UI.index(".padding(.horizontal, 12)",UI.index("private var appPanelContent")))
        self.assertNotIn("LinearGradient(colors: [.white.opacity(0.58)",UI)

    def test_landscape_rotation_no_intermediate_rectangles(self):
        for x in ("settleOverlayAfterRotation()", "overlay_rotation_suspended",
                  "overlay_rotation_resumed","overlay.alpha = 0",
                  "overlay.alpha = 1",
                  "let usableHeight = max(CGFloat(260)",
                  "height = open ? min(cardHeight + 84, usableHeight) : 72",
                  "overlay.layer.masksToBounds = true",
                  "if stableSamples >= 4", "rotationGeneration == token",
                  "No real scene rotation"):
            self.assertIn(x,UI)
        self.assertIn('let orientationList = appData["UISupportedInterfaceOrientations"]', UI)
        self.assertIn("portrait_only",UI)
        self.assertIn("landscape_supported",UI)
        self.assertNotIn("appData[\"UISupportedInterfaceOrientations\"] = ",UI)
        for x in ("host.frame =","original.frame =","orientationLock =",
                  "UISupportedInterfaceOrientations~ipad","runApp(multitask: true)"):
            self.assertNotIn(x,UI)

    def test_single_jitless_certificate_owner_and_legacy_fallback(self):
        for x in ('jitless_begin =', 'original_jit=source[i:j]',
                  "if #available(iOS 17.0, *)", "ScarletSigningReadinessPanel()",
                  "LCJITLessDiagnoseView()", "if jitless_begin not in source"):
            self.assertIn(x,PATCH)
        self.assertIn('Text("JIT-Less · 인증서")',PANEL)
        self.assertIn('Label("JIT-Less 모드 진단"',PANEL)
        self.assertIn("SCARLET_JITLESS_SINGLE_DIAGNOSTIC",PANEL)
        self.assertIn("LCJITLessDiagnoseView()",PANEL)
        self.assertIn('Label("SideStore 인증서 받기"',PANEL)
        self.assertIn('Label("P12 파일 선택"',PANEL)

    def test_cert_origin_categorized_without_private_key_in_logs(self):
        for x in ("oldPortalSerials","oldActiveSerial",
                  "DeveloperPortalProxy.shared.fetchCertificates",
                  "scarlet.cert.new_apple_portal",
                  "scarlet.cert.existing_active",
                  "scarlet.cert.existing_portal",
                  "scarlet.cert.existing_stored",
                  "portalVerified"):
            self.assertIn(x,WORKER)
        self.assertIn("lastResolution",TRANSPORT)
        self.assertIn('"certificate", "provider_origin_checked"',PANEL)
        self.assertIn('"source"',RECORDER)
        for x in ("pendingCertificateOrigin", "new_apple_portal",
                  "existing_active", "existing_stored", "external_file",
                  '"certificate", "p12_origin_at_storage"'):
            self.assertIn(x,PANEL)
        for forbidden in ("fields: [\"serialNumber\"", "fields: [\"p12\"", "revokeCertificate("):
            self.assertNotIn(forbidden,WORKER+PANEL)
if __name__=="__main__":
    unittest.main()
