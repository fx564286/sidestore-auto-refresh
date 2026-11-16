"""P75: P61 slot list/change previously crossed the selected Apple Team boundary.
The native Xcode CI validates the injected, concatenated SideStore Swift worker;
these static assertions do not constitute a device authorization test.
"""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORKER=(ROOT/'integration/ScarletDeviceInstallAgent.swift.txt').read_text()
WIRE=(ROOT/'integration/wire_scarlet_auth.py').read_text()
class TeamScopedSlotManager(unittest.TestCase):
    def test_list_is_team_scoped_and_switch_serialized(self):
        listing=WORKER.split('static func listManagedSlots(',1)[1].split('@objc(setManagedSlot:',1)[0]
        self.assertIn('ScarletTeamOperationGate.shared.claim()',listing)
        self.assertIn('ScarletTeamOperationGate.shared.release()',listing)
        self.assertIn('ScarletInstallTeamAuthority.activeOwnership()',listing)
        self.assertIn('InstalledApp.all(in: context).filter {',listing)
        self.assertIn('ScarletInstallTeamAuthority.appBelongsToOwner($0, owner: owner)',listing)
        self.assertIn('reply("[]", "selected_account_owner_unverified")',listing)
        self.assertNotIn('let apps = InstalledApp.all(in: context)\n',listing)
    def test_action_rechecks_team_before_any_upstream_operation(self):
        action=WORKER.split('static func setManagedSlot(',1)[1]
        for marker in ('ScarletSlotOperationGate.shared.claim()',
          'ScarletTeamOperationGate.shared.claim()',
          'ScarletInstallTeamAuthority.activeOwnership()',
          'guard ScarletInstallTeamAuthority.appBelongsToOwner(app,',
          'reply(false, "selected_account_app_mismatch")',
          'app.resignedBundleIdentifier != Bundle.Info.activeBundleIdentifier',
          'app.bundleIdentifier != StoreApp.altstoreAppID'):
            self.assertIn(marker,action)
        self.assertLess(action.index('selected_account_app_mismatch'),
          action.index('AppManager.shared.appsToDeactivate(for: app)'))
        self.assertLess(action.index('selected_account_app_mismatch'),
          action.index('AppManager.shared.activate(app,'))
        self.assertLess(action.index('selected_account_app_mismatch'),
          action.index('AppManager.shared.deactivate(app,'))
        self.assertIn('AppManager.shared.activate(app, presentingViewController: nil)', action)
        self.assertIn('AppManager.shared.deactivate(app, presentingViewController: nil)', action)
    def test_single_swift_compilation_unit_contains_shared_gate(self):
        self.assertIn('ScarletGuestSavedAccounts.swift.txt',WIRE)
        self.assertIn('ScarletDeviceInstallAgent.swift.txt',WIRE)
        self.assertIn('source.rstrip() + "\\n\\n" + extra',WIRE)
    def test_no_mutation_of_cross_team_records(self):
        assert 'app.isActive = active' not in WORKER
        assert 'AppManager.shared.deleteApp(' not in WORKER
        assert 'clearActiveCertificate()' not in WORKER
if __name__=='__main__': unittest.main()
