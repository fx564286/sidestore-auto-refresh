"""P82: Settings Apple ID is the single owner for device IPA installation."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
LOGIN = (ROOT/'HostApp/ScarletAppleIDLoginSheet.swift').read_text()
XPC = (ROOT/'HostApp/ScarletAuthXPCSupport.swift').read_text()
SETTINGS = (ROOT/'integration/apply_scarlet_host.py').read_text()
WORKFLOW = (ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class P82InstallAccountOwner(unittest.TestCase):
    def test_duplicate_account_selection_ui_removed(self):
        for forbidden in ('ScarletInstallTeamPicker', 'showInstallTeamPicker',
            'install_team_picker_requested', 'SCARLET_INSTALL_TEAM_PICKER',
            'SCARLET_SELECT_INSTALL_TEAM', 'install_team_selected'):
            self.assertNotIn(forbidden, HOST + LOGIN, forbidden)
        self.assertIn('SCARLET_SETTINGS_SWITCH_APPLE_ID', SETTINGS)
        self.assertIn('SCARLET_SETTINGS_ACTIVE_APPLE_ID', SETTINGS)
        self.assertIn('SCARLET_SETTINGS_ADD_LOGIN', SETTINGS)
    def test_async_single_active_account_readback_precedes_files(self):
        action = HOST.split('case .serviceInstallIPA:', 1)[1].split(
            'case .localOpenEmbeddedSideStore,', 1)[0]
        for key in ('guard !deviceInstallAccountPreflightRunning else { return }',
            'ScarletNativeSavedAccounts.list()',
            'snapshot.status == "ready", active.count == 1',
            '.prepareInstallTeam(account.teamID)',
            'verified.count == 1', 'verified[0].id == account.id',
            'verified[0].teamID == account.teamID',
            'selectedInstallAccountID = account.id',
            'selectedInstallTeamID = account.teamID',
            'showGuestFilePicker = true'):
            self.assertIn(key, action, key)
        self.assertLess(action.index('selectedInstallAccountID = account.id'),
                        action.index('showGuestFilePicker = true'))
        self.assertNotIn('ScarletNativeSavedAccounts.activate(', action)
        self.assertNotIn('issueInstallCertificate(', action)
    def test_account_changes_during_ipa_staging_fail_closed(self):
        stage = HOST.split('private func prepareDeviceIPAInstall(',1)[1].split(
            'private func ',1)[0]
        for key in ('let pinnedAccountID = selectedInstallAccountID',
            'let pinnedTeamID = selectedInstallTeamID',
            'let accountState = await ScarletNativeSavedAccounts.list()',
            'activeAccounts.count == 1',
            'activeAccounts[0].id == pinnedAccountID',
            'activeAccounts[0].teamID == pinnedTeamID',
            'active_account_changed_before_install',
            'teamID: pinnedTeamID'):
            self.assertIn(key,stage,key)
        self.assertLess(stage.index('activeAccounts[0].id == pinnedAccountID'),
                        stage.index('ScarletDeviceInstaller.install('))
    def test_team_certificate_pin_preserved_and_no_auto_account_switch(self):
        self.assertIn('client.scarletPrepareInstallTeam(teamID',XPC)
        self.assertIn('client.scarletSelectAuthAccount(id)',XPC)
        self.assertIn('selected_team_certificate_missing',HOST)
        self.assertIn('readiness.canRequestNativeRefresh',HOST)
        self.assertIn('ScarletDeviceInstaller.install(',HOST)
        self.assertNotIn('removeCertificate()',HOST)
        self.assertNotIn('revokeCertificate(',HOST)
    def test_build_version_and_release_routed_for_new_branch(self):
        for value in ('fix/scarlet-v48-r6p82-settings-active-install-20261116',
                      '--host-build-version 3.8.82',
                      'Scarlet-Crystal-V48-R6P82-ACCOUNT-INSTALL-UNSIGNED.ipa',
                      'scarlet-v48-r6p82-account-install-unsigned-20261116',
                      '"r6p82"'):
            self.assertIn(value,WORKFLOW,value)

if __name__=='__main__': unittest.main()
