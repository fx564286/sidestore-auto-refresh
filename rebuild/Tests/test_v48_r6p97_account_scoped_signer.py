"""P97: Owner-scoped certificate serial binding, no cross-account implicit signer inheritance."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[2]
SRC=(ROOT/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()
HOST=(ROOT/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()

class AccountScopedSigner(unittest.TestCase):
    def test_keychain_serial_pinned_for_exact_apple_id_and_team(self):
        self.assertIn('private static let signerService =',SRC)
        self.assertIn('kSecAttrAccount as String: id + "|" + teamID',SRC)
        self.assertIn('kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly',SRC)
        self.assertIn('static func pinnedSignerSerial(appleID: String, teamID: String)',SRC)
        self.assertIn('static func bindSignerSerial(_ serial: String, appleID: String,',SRC)
        self.assertIn('return pinnedSignerSerial(appleID: id, teamID: teamID) == normalized',SRC)
        self.assertNotIn('SecItemDelete(',SRC)
    def test_account_list_not_ready_from_other_accounts_team_ou(self):
        body=SRC.split('static func savedRows()',1)[1].split('static func switchTo(',1)[0]
        self.assertIn('for: slot.teamID, appleID: slot.email',body)
    def test_native_certificate_selection_never_unpinned(self):
        body=SRC.split('static func matchingCertificate(',1)[1].split('static func hasValidSigningCertificate',1)[0]
        self.assertIn('pinnedSignerSerial(',body)
        self.assertIn('appleID: owner, teamID: teamID',body)
        self.assertIn('$0.serialNumber.lowercased() == pinned',body)
        self.assertNotIn('return manager.getAllLocalCertificates().first {\n            certificateBelongsToTeam($0, teamID: teamID)',body)
    def test_import_and_explicit_portal_issue_bind_to_active_owner(self):
        body=SRC.split('static func importArchive(',1)[1].split('static func issue(teamID: String)',1)[0]
        self.assertIn('guard let owner = await activeOwnership()',body)
        self.assertIn('ScarletAccountVault.bindSignerSerial(',body)
        issue=SRC.split('static func issue(teamID: String)',1)[1].split('extension ScarletGuestSignInAgent',1)[0]
        self.assertIn('DeveloperPortalProxy.shared.fetchCertificates(team: team)',issue)
        self.assertIn('ScarletAccountVault.bindSignerSerial(',issue)
        self.assertIn('owner.appleID',issue)
        self.assertIn('DeveloperPortalProxy.shared.createCertificate(',issue)
    def test_native_error_relay_preserves_account_binding_reasons(self):
        for x in ('selected_account_signer_binding_failed','selected_account_owner_unverified','selected_account_owner_changed'):
            self.assertIn('"'+x+'"',HOST)

if __name__ == '__main__': unittest.main()
