"""P90: Apple ID AND Team ID must own each native operation.
These are source-contract tests; the signed-iPhone ownership result needs
independent verification, including two IDs that share a Developer Team.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
S=(R/'integration/ScarletGuestSavedAccounts.swift.txt').read_text()
I=(R/'integration/ScarletDeviceInstallAgent.swift.txt').read_text()
F=(R/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
G=(R/'diagnostics/scarlet_no_repeat_gate.py').read_text()
B=(R/'integration/apply_scarlet_host.py').read_text()
class AccountOwnership(unittest.TestCase):
 def test_side_store_original_account_relation_is_required(self):
  a=S.split('static func activeOwnership()',1)[1].split('static func validTeam(',1)[0]
  for mark in ('AuthManager.shared.currentAppleID', 'team.identifier',
   '$0.isActiveTeam', '$0.account?.isActiveAccount == true',
   '$0.account?.appleID.caseInsensitiveCompare(account) == .orderedSame'):
   self.assertIn(mark,a)
  self.assertIn('app.team?.account?.appleID.caseInsensitiveCompare(owner.appleID)',S)
 def test_install_binds_owner_at_entry_and_validates_returned_app(self):
  a=I.split('static func install(_ payload:',1)[1].split('private static func safeFailureReason',1)[0]
  for mark in ('owner.teamID == expectedTeamID',
   'selected_account_team_mismatch',
   'ScarletInstallTeamAuthority.appBelongsToOwner(',
   'installed_app_owner_unverified'):
   self.assertIn(mark,a)
  self.assertLess(a.index('owner.teamID == expectedTeamID'),a.index('AppManager.shared.install('))
  self.assertLess(a.index('AppManager.shared.install('),a.index('installed_app_owner_unverified'))
 def test_slot_list_and_mutation_check_account_not_just_team(self):
  a=I.split('@objc(listManagedSlots:',1)[1]
  self.assertGreaterEqual(a.count('ScarletInstallTeamAuthority.activeOwnership()'),2)
  self.assertGreaterEqual(a.count('ScarletInstallTeamAuthority.appBelongsToOwner('),3)
  self.assertIn('selected_account_app_mismatch',a)
  self.assertIn('AppManager.shared.appsToDeactivate(for: app)',a)
 def test_native_refresh_filters_by_original_app_owner(self):
  self.assertIn('let selectedAppleID = owner.appleID',F)
  self.assertIn('let currentAppleID = owner?.appleID',F)
  self.assertIn('$0.team?.account?.appleID.caseInsensitiveCompare(',F)
  self.assertNotIn('$0.team == nil',F)
  self.assertIn('profile.teamIdentifier == owner.teamID',F)
  self.assertIn('record.team = team',F)
 def test_append_history_is_verified_and_embedded_as_full_diagnostics(self):
  self.assertIn('scarlet_remediation_history_appendix.json', G)
  self.assertIn('data["entries"].extend(extra["entries"])', G)
  self.assertIn('audit["entries"].extend(appendix["entries"])', B)
  self.assertIn('history_bytes = json.dumps(audit', B)
 def test_no_destructive_cross_account_reset(self):
  for forbidden in ('SecItemDelete(', 'revokeCertificate(',
   'removeItem(at: hostURL)', 'app.isActive = active'):
   self.assertNotIn(forbidden,S+I+F)
if __name__=='__main__':unittest.main()
