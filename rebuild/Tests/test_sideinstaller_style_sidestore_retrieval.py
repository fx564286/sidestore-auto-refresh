"""Contract for SideInstaller-compatible in-app SideStore P12 retrieval."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
BRIDGE=(ROOT/'HostApp/ScarletCertificateXPCSupport.swift').read_text()
WORKER=(ROOT/'integration/ScarletGuestCertificateAgent.swift.txt').read_text()
WIRE=(ROOT/'integration/wire_scarlet_auth.py').read_text()

class SideInstallerStyleRetrieval(unittest.TestCase):
    def test_two_distinct_actions_directly_in_one_app(self):
        issue=UI.index('Label("SideStore에서 인증서 받기"')
        retrieve=UI.index('Label("SideInstaller 방식 · SideStore 인증서 가져오기"')
        files=UI.index('Label("다른 인증서 가져오기"')
        self.assertLess(issue,retrieve)
        self.assertLess(retrieve,files)
        self.assertIn('SCARLET_P12_SIDEINSTALLER_STYLE_IMPORT',UI)
        self.assertIn('retrieveSideInstallerStyleCertificate()',UI)
        self.assertNotIn('sideinstaller://',UI)
        self.assertNotIn('UIApplication.shared.open(',UI)

    def test_retrieval_does_not_request_new_or_revoke(self):
        section=WORKER.split('@objc(retrieve:)')[1].split('@MainActor\n    private static func report')[0]
        self.assertIn('CertificateManager.shared.activeCertificate',section)
        self.assertNotIn('CertificateProvisioningFlow(',section)
        self.assertNotIn('revokeCertificate(',section)
        self.assertNotIn('DeveloperPortalProxy',section)
        self.assertIn('stored_p12_missing',section)
        self.assertIn('retrieveSideStoreCertificate',BRIDGE)
        self.assertIn('scarletRetrieveCertificate(id)',BRIDGE)
        self.assertIn('scarletRetrieveCertificate:(NSString*)requestID',WIRE)
        self.assertIn('selector(retrieve:)',WIRE)

    def test_validation_and_sideinstaller_in_lc_fallback(self):
        self.assertIn('importExportedP12()',UI)
        self.assertIn('hostTeam == archiveTeam',UI)
        self.assertIn('isConfirmingCertReplacement',UI)
        self.assertIn('LCUtils.certificateData()',UI)
        self.assertIn('sideinstaller_style_local_fallback',UI)
        self.assertIn('sideinstaller_style_retrieval_missing',UI)

if __name__=='__main__': unittest.main()
