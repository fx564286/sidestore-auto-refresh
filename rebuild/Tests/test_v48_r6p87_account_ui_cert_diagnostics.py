"""P87: regression contracts from P86 on-device failure (not device proof)."""
from pathlib import Path
import unittest
R = Path(__file__).resolve().parents[1]
UI = (R / 'integration/apply_scarlet_host.py').read_text()
CERT = (R / 'HostApp/ScarletSigningReadinessPanel.swift').read_text()
class P87Accounts(unittest.TestCase):
    def test_switch_updates_verified_snapshot_without_generic_login_notification(self):
        body = UI.split('private func scarletSwitchToSavedAccount(',1)[1].split('    new_section="""',1)[0]
        self.assertIn('scarletSavedAccounts = readback.accounts', body)
        self.assertIn('await scarletEnsureCertificateForActiveAccount()', body)
        self.assertNotIn('NotificationCenter.default.post(', body)
        self.assertNotIn('await scarletReloadSavedAccounts()', body)
    def test_account_cell_no_unnatural_divider(self):
        body=UI.split('Section {\n                    if !scarletSavedAccounts.isEmpty',1)[1].split('} header: {\n                    Text("계정")',1)[0]
        self.assertNotIn('VStack(alignment: .leading, spacing: 10)',body)
        self.assertIn('.buttonStyle(.plain)',body)
        self.assertNotIn('Divider()',body)
        self.assertIn('SCARLET_SETTINGS_ADD_LOGIN',body)
    def test_p12_import_fails_closed_with_distinct_error_reasons(self):
        body=CERT.split('private func importExportedP12(',1)[1].split('    new_section="""',1)[0]
        for item in ('p12_decode_or_password_invalid', 'active_account_unavailable',
                     'p12_selected_account_team_mismatch',
                     'ScarletNativeSavedAccounts.importSelectedTeamCertificate('):
            self.assertIn(item,body)
        self.assertNotIn('archive_team_differs_from_signed_host',body)
        self.assertNotIn('defaults.set(archive, forKey: "LCCertificateData")',body)
if __name__ == '__main__': unittest.main()
