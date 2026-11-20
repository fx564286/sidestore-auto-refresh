"""R6P121: distinct, explicit, owner-fenced existing SideStore P12 recovery."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
UI = (ROOT / 'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
WORKFLOW = (ROOT / '.github/workflows/scarlet-paired-engines-build.yml').read_text()
ISSUE = UI.split('private func requestNativeCertificate()', 1)[1].split(
    'private func retrieveSideInstallerStyleCertificate()', 1)[0]
RETRIEVE = UI.split('private func retrieveSideInstallerStyleCertificate()', 1)[1].split(
    '// Stage 3:', 1)[0]
BUTTONS = UI.split('Button(action: requestManualRefresh)', 1)[1].split(
    '// P92:', 1)[0]


class ExistingAfterIssueFailure(unittest.TestCase):
    def test_new_certificate_action_still_requires_fresh_apple_serial(self):
        self.assertIn('.issueFreshInstallCertificate(owner.teamID)', ISSUE)
        self.assertIn('result.0 && result.1 == "ready_issued_apple"', ISSUE)
        self.assertNotIn('retrieveSideInstallerStyleCertificate()', ISSUE)
        self.assertIn('offersExistingCertificateRecovery = false', ISSUE)
        self.assertIn('case "selected_team_certificate_portal_failed":', ISSUE)
        self.assertIn('"selected_team_certificate_quota_reached":', ISSUE)
        self.assertIn('offersExistingCertificateRecovery = true', ISSUE)

    def test_portal_failure_exposes_separate_explicit_existing_p12_action(self):
        self.assertIn('if offersExistingCertificateRecovery {', BUTTONS)
        self.assertIn('Button(action: retrieveSideInstallerStyleCertificate)', BUTTONS)
        self.assertIn('Label("기존 SideStore 인증서 사용"', BUTTONS)
        self.assertIn('SCARLET_P12_EXISTING_AFTER_ISSUE_FAILURE', BUTTONS)
        self.assertEqual(UI.count('Label("SideStore 인증서 받기"'), 1)
        self.assertEqual(UI.count('Label("P12 파일 선택"'), 1)

    def test_native_p12_read_is_owner_fenced_and_explicitly_checked(self):
        self.assertIn('let before = await ScarletNativeSavedAccounts.list()', RETRIEVE)
        self.assertIn('before.accounts.filter({ $0.active }).count == 1', RETRIEVE)
        self.assertIn('let owner = before.accounts.first(where: { $0.active })', RETRIEVE)
        self.assertIn('let after = await ScarletNativeSavedAccounts.list()', RETRIEVE)
        self.assertIn('$0.active && $0.id == owner.id && $0.teamID == owner.teamID', RETRIEVE)
        self.assertIn('guard imported else { return }', RETRIEVE)
        self.assertIn('let imported = await importExportedP12()', RETRIEVE)
        self.assertIn('"sideinstaller_style_retrieval_finished"', RETRIEVE)
        self.assertNotIn('createCertificate(', RETRIEVE)
        self.assertNotIn('revokeCertificate(', RETRIEVE)

    def test_new_unique_ci_release_identity(self):
        self.assertIn('fix/scarlet-v48-r6p121-existing-cert-recovery-20261120', WORKFLOW)
        self.assertIn('--host-build-version 3.8.121', WORKFLOW)
        self.assertIn('version="3.8.121"', WORKFLOW)
        self.assertIn('asset="Scarlet-Crystal-V48-R6P121-EXISTING-CERT-RECOVERY-UNSIGNED.ipa"', WORKFLOW)
        self.assertIn('tag=scarlet-v48-r6p121-existing-cert-recovery-unsigned-20261120', WORKFLOW)


if __name__ == '__main__':
    unittest.main()
