"""V6 scope: authentic in-app certificate flow + exact main-tab glass."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()
SIGN=(ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
MAIN_GLASS=(ROOT/"HostApp/ScarletNativeGlass.swift").read_text()
SUPPORT=(ROOT/"HostApp/ScarletCertificateXPCSupport.swift").read_text()
WIRE=(ROOT/"integration/wire_scarlet_auth.py").read_text()
WORKER=(ROOT/"integration/ScarletGuestCertificateAgent.swift.txt").read_text()

class InAppCertAndGlassContracts(unittest.TestCase):
    def test_certificate_is_one_native_screen_without_external_launch(self):
        self.assertIn('Label("SideStore 인증서 받기"',SIGN)
        self.assertIn('Label("P12 파일 선택"',SIGN)
        self.assertNotIn('Label("추가 인증서 관리"',SIGN)
        self.assertNotIn('Label("SideInstaller 방식 · SideStore 인증서 가져오기"',SIGN)
        self.assertIn('retrieveSideInstallerStyleCertificate()',SIGN)
        self.assertIn('sideinstaller_style_local_fallback',SIGN)
        self.assertIn('sideinstaller_style_retrieval_missing',SIGN)
        self.assertIn("ScarletNativeCertificateTransport.shared.obtain()",SIGN)
        self.assertNotIn('UIApplication.shared.open(',SIGN)
        self.assertNotIn("sideinstaller://",SIGN)
        self.assertIn("isConfirmingCertReplacement",SIGN)
        self.assertIn("native_provider_same_certificate",SIGN)
        self.assertNotIn('Label("SideStore 인증서 재확인"',SIGN)
        self.assertIn("hostTeam == archiveTeam",SIGN)
        self.assertIn("replacement_readback_failed",SIGN)
        i=SIGN.index('Label("SideStore 인증서 받기"')
        j=SIGN.index('Label("P12 파일 선택"')
        self.assertLess(i,j)

    def test_worker_uses_authorized_original_provisioning_no_revoke(self):
        for fragment in ("CertificateProvisioningFlow(handler: nil)",
                         "AuthManager.shared.getAuthenticatedTeam()",
                         'team.identifier == "P8EZT3U5N4"',
                         "CertificateManager.shared.activeCertificate",
                         "scarlet.certificate.portal_error"):
            self.assertIn(fragment,WORKER)
        self.assertIn("ALTAccount(appleID: email, identifier: dsid)",WORKER)
        self.assertIn("DeveloperPortalProxy.shared.fetchTeams",WORKER)
        self.assertNotIn('revokeCertificate(',WORKER)
        for fragment in ("scarletIssueCertificate", "scarletCertificateCompleted",
                         "ScarletGuestCertificateCompleted"):
            self.assertIn(fragment,WIRE)
        self.assertIn("scarletIssueCertificate(id)",SUPPORT)
        self.assertIn("scarletRetrieveCertificate(id)",SUPPORT)
        self.assertIn("retrieveSideStoreCertificate()",SUPPORT)
        self.assertIn("@objc(retrieve:)",WORKER)
        self.assertIn("CertificateManager.shared.activeCertificate",WORKER)
        self.assertIn('stored_p12_missing',WORKER)
        self.assertIn("CheckedContinuation<(Data, String), Error>",SUPPORT)
        self.assertNotIn("URLSession",SUPPORT)
        self.assertNotIn("base64EncodedString()",SUPPORT)

    def test_guest_reuses_main_tab_clear_glass_not_regular(self):
        self.assertIn("let glass = UIGlassEffect(style: .clear)",MAIN_GLASS)
        self.assertIn("SCNativeLiquidGlassSurface(cornerRadius: radius, showsRim: false)",UI)
        # V26: one native surface is geometrically animated between the
        # 62pt button and fixed 28pt-radius glass card. No duplicate glass.
        self.assertIn("glassPlate(radius: isOpen ? 28 : 31)",UI)
        self.assertNotIn("ScarletUIKitGlassBackdrop",UI)
        self.assertIn("x: (bounds.width - w) / 2",UI)
        self.assertIn("let w = min(CGFloat(430)",UI)
        # V25: expanded window intercepts outside taps for modal dismiss;
        # collapsed 62pt button still passes all other guest touches through.
        self.assertIn("if isExpanded {", UI)
        self.assertIn("return hypot(point.x - buttonCenter.x,", UI)
        self.assertNotIn("return isExpanded && panelRect.contains(point)", UI)

    def test_remove_requested_visible_brand_label(self):
        self.assertNotIn("홍수정",UI)
        self.assertNotIn("홍수정",SIGN)
        self.assertIn('Label("앱 목록"',UI)
        self.assertIn("try await app.runApp()", (ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text())

if __name__=="__main__":
    unittest.main()
