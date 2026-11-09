"""Contract for SideInstaller-compatible in-app SideStore P12 retrieval."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
BRIDGE=(ROOT/'HostApp/ScarletCertificateXPCSupport.swift').read_text()
WORKER=(ROOT/'integration/ScarletGuestCertificateAgent.swift.txt').read_text()
WIRE=(ROOT/'integration/wire_scarlet_auth.py').read_text()

class SideInstallerStyleRetrieval(unittest.TestCase):
    def test_exactly_two_user_actions_no_nested_menu(self):
        issue=UI.index('Label("SideStore 인증서 받기"')
        files=UI.index('Label("P12 파일 선택"')
        self.assertLess(issue,files)
        self.assertEqual(UI.count('Label("SideStore 인증서 받기"'),1)
        self.assertEqual(UI.count('Label("P12 파일 선택"'),1)
        for old in ("추가 인증서 관리", "권한 상태 다시 검사",
                    'Label("SideStore 수동 새로고침"',
                    'Label("JIT-Less 모드 진단"'):
            self.assertNotIn(old,UI[UI.index('    var body: some View {'):])
        self.assertIn('SCARLET_P12_NATIVE_ISSUE',UI)
        self.assertIn('SCARLET_P12_IMPORT_FROM_FILES',UI)
        self.assertIn('retrieveSideInstallerStyleCertificate()',UI)
        self.assertIn('SideInstaller-style retrieval is an internal fallback',UI)
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
