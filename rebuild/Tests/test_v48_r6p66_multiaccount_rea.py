"""P66: verify the actual multi-login execution path, not cosmetic buttons.

Static guards complement but NEVER replace Xcode, signed iPhone account switching,
Apple 2FA and post-switch signing tests.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
VAULT=(ROOT/'integration/ScarletGuestSavedAccounts.swift.txt').read_text()
AGENT=(ROOT/'integration/ScarletGuestSignInAgent.swift.txt').read_text()
XPC=(ROOT/'integration/wire_scarlet_auth.py').read_text()
HOST=(ROOT/'HostApp/ScarletAuthXPCSupport.swift').read_text()
SHEET=(ROOT/'HostApp/ScarletAppleIDLoginSheet.swift').read_text()
LC=(ROOT/'integration/apply_scarlet_host.py').read_text()

class VerifiedAccountRoutes(unittest.TestCase):
    def test_native_settings_add_account_is_real_sheet(self):
        self.assertIn('SCARLET_SETTINGS_ADD_LOGIN', LC)
        self.assertIn('Label(scarletLoginVerified == true || !scarletSavedAccounts.isEmpty', LC)
        self.assertIn('scarletShowAppleLogin = true',LC)
        self.assertNotIn('scarletShowAccountAdditionNotice', LC)
        self.assertNotIn('단일 활성 계정만 유지합니다', LC)
        self.assertIn('SCARLET_ADD_SECOND_APPLE_ID',SHEET)
        self.assertIn('ScarletNativeSavedAccounts.list()',SHEET)
        self.assertIn('ScarletNativeSavedAccounts.activate(id)',SHEET)
    def test_per_account_keychain_not_defaults_or_logs(self):
        for marker in ('kSecClassGenericPassword','kSecAttrService',
                       'kSecAttrAccount','kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly',
                       'SecItemAdd','SecItemCopyMatching','SecItemUpdate',
                       'captureCurrent()','switchTo(', 'await activate(previous)'):
            self.assertIn(marker, VAULT)
        for forbidden in ('print(slot)', 'password = slot.password; print',
                          'UserDefaults.standard.set(slot.password',
                          'UserDefaults.standard.set(slot.xcodeToken'):
            self.assertNotIn(forbidden,VAULT)
    def test_cannot_replace_authenticated_session_without_backup(self):
        self.assertIn('if persistedState() && previousSlot == nil',AGENT)
        self.assertIn('ScarletAccountVault.save(previousSlot)',AGENT)
        self.assertIn('await ScarletAccountVault.activate(previousSlot)',AGENT)
        self.assertIn('scarlet.auth.rollback_unverified',AGENT)
        self.assertIn('throw NSError(domain: "scarlet.auth.keychain_roundtrip_failed"',AGENT)
        self.assertNotIn('finish(id, code: -3401, domain:',AGENT)
        self.assertIn('ScarletAccountVault.save(added)',AGENT)
        self.assertIn('current_session_unverified', VAULT)
        self.assertIn('existing.count < maxAccounts',VAULT)
        self.assertIn('account_activation_unverified',VAULT)
    def test_team_is_bound_to_account_not_forced_to_host_team(self):
        self.assertIn('$0.account?.objectID == account.objectID',VAULT)
        self.assertIn('team.account?.objectID == account.objectID',AGENT)
        self.assertIn('}) ?? portalTeams.first else',AGENT)
        self.assertIn('scarletInvalidateCachedTeam()',AGENT)
        self.assertIn('requireHostTeam: Bool = true',AGENT)
        self.assertIn('requireHostTeam: false',AGENT)
    def test_xpc_has_list_and_switch_with_bounded_timeouts(self):
        for marker in ('scarletAuthAccounts:', 'scarletSelectAuthAccount:',
                       '@selector(listAccounts:)', '@selector(selectAccount:reply:)'):
            self.assertIn(marker,XPC)
        for marker in ('ScarletStoredAppleAccount', 'ScarletNativeSavedAccounts',
                       'client.scarletAuthAccounts', 'client.scarletSelectAuthAccount',
                       'timeout_state_unknown','scarletAccountWasSwitched()'):
            self.assertIn(marker,HOST)
        self.assertIn('import Security',XPC)
        self.assertIn('import Minimuxer',XPC)
        self.assertIn('ScarletGuestSavedAccounts.swift.txt',XPC)
    def test_does_not_interfere_guest_layout_or_signed_host(self):
        self.assertNotIn('ScarletFullscreenSceneStack.swift', '\n'.join(
            ('ScarletGuestSavedAccounts.swift.txt','ScarletAppleIDLoginSheet.swift')))
        self.assertNotIn('removeCertificate(',VAULT)
        self.assertNotIn('clearSignInInfo(',VAULT)

if __name__ == '__main__': unittest.main()
