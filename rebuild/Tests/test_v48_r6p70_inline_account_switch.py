"""P70: native Settings must expose each stored Apple ID without an extra login sheet."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
PATCH=(R/'integration/apply_scarlet_host.py').read_text()
SHEET=(R/'HostApp/ScarletAppleIDLoginSheet.swift').read_text()
XPC=(R/'HostApp/ScarletAuthXPCSupport.swift').read_text()
WORKFLOW=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class InlineAccountSwitch(unittest.TestCase):
    def test_settings_reads_keychain_backed_account_rows(self):
        for key in ('@State private var scarletSavedAccounts:',
                    'ForEach(scarletSavedAccounts) { row in', 'Text(row.id)', '.lineLimit(1)',
                    'SCARLET_SETTINGS_ACTIVE_APPLE_ID',
                    'SCARLET_SETTINGS_SWITCH_APPLE_ID',
                    'await ScarletNativeSavedAccounts.list()',
                    'scarletReloadSavedAccounts()',
                    'SCARLET_SETTINGS_ADD_LOGIN'):
            self.assertIn(key, PATCH)
    def test_switch_calls_existing_verified_worker_and_checks_readback(self):
        for key in ('await ScarletNativeSavedAccounts.activate(id)',
                    'readback.accounts.filter({ $0.active }).count == 1',
                    '$0.id == id && $0.active',
                    'settings_account_switch_verified',
                    'settings_account_switch_readback_failed',
                    'scarletSwitchingAccountID == nil',
                    'scarletAccountReadGeneration'):
            self.assertIn(key, PATCH)
        self.assertIn('client.scarletSelectAuthAccount(id)', XPC)
    def test_add_login_opens_credential_form_without_second_click(self):
        self.assertIn('startsWithAdditionalLogin: true', PATCH)
        self.assertIn('explicitlyReauthenticating = startsWithAdditionalLogin', SHEET)
        self.assertIn('SCARLET_APPLE_ID_FIELD', SHEET)
        self.assertIn('SCARLET_ADD_SECOND_APPLE_ID', SHEET)
    def test_preserve_existing_native_settings_and_unique_ipa(self):
        self.assertIn('LCSettingsView()', (R/'HostApp/ScarletIntegratedHostView.swift').read_text())
        self.assertIn('import SwiftUI\\nimport SideStoreSupport\\n', PATCH)
        self.assertIn('ScarletSigningReadinessPanel()', PATCH)
        self.assertIn('SCARLET_NATIVE_DIAGNOSTICS_ENTRY', PATCH)
        self.assertIn('3.8.70', WORKFLOW)
        self.assertIn('Scarlet-Crystal-V48-R6P70-ACCOUNT-SWITCH-UNSIGNED.ipa', WORKFLOW)
if __name__ == '__main__':unittest.main()
