"""P89 source acceptance: UI navigation ownership and native per-account p12 bridge.
Source tests cannot verify iPhone geometry or a successful Apple server round trip.
"""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
UI=(R/'Sources/ScarletIndependentUI/ScarletIndependentShell.swift').read_text()
PATCH=(R/'integration/apply_scarlet_host.py').read_text()
PANEL=(R/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
HOST=(R/'HostApp/ScarletAuthXPCSupport.swift').read_text()
GUEST=(R/'integration/ScarletGuestSavedAccounts.swift.txt').read_text()
XPC=(R/'integration/wire_scarlet_auth.py').read_text()
class P89NativeAccountCertificate(unittest.TestCase):
 def test_settings_has_native_navigation_edge_and_inline_title(self):
  body=UI.split('if tab == .settings {',1)[1].split('} else if tab == .tweaks',1)[0]
  self.assertIn('nativeSettings()',body)
  self.assertNotIn('.scarletIndependentScrollEdge()',body)
  self.assertIn('.navigationBarTitleDisplayMode(.inline)',PATCH)
 def test_per_account_rows_have_one_form_row_each(self):
  area=PATCH.split('if !scarletSavedAccounts.isEmpty {',1)[1].split('} else if scarletLoginVerified == true',1)[0]
  self.assertIn('ForEach(scarletSavedAccounts) { row in',area)
  self.assertIn('Button {',area)
  self.assertIn('.buttonStyle(.plain)',area)
  self.assertNotIn('Divider()',area)
  self.assertNotIn('.listRowSeparator(.hidden)',area)
 def test_external_p12_goes_to_selected_team_not_host_userdefaults(self):
  body=PANEL.split('private func importExportedP12(',1)[1].split('    var body:',1)[0]
  self.assertIn('rows.accounts.filter({ $0.active }).count == 1',body)
  self.assertIn('active.teamID == team',body)
  self.assertIn('ScarletNativeSavedAccounts.importSelectedTeamCertificate(',body)
  self.assertNotIn('defaults.set(archive, forKey: "LCCertificateData")',body)
  self.assertNotIn('archive_team_differs_from_signed_host',body)
 def test_guest_requires_team_and_portal_and_rollback(self):
  body=GUEST.split('static func importArchive(',1)[1].split('    // P86:',1)[0]
  for fragment in ('ensureActiveTeamForRefresh(requireHostTeam: false)',
   'CertificateManager.parse(archive, password: password)',
   'certificateBelongsToTeam(certificate, teamID: teamID)',
   'fetchCertificates(team: team)',
   'manager.setActiveCertificate(certificate)',
   'selected_team_certificate_readback_failed'):
   self.assertIn(fragment,body)
  self.assertIn('try? manager.setActiveCertificate(original)',body)
 def test_xpc_import_is_explicit_and_time_limited(self):
  self.assertIn('scarletImportInstallCertificate',HOST)
  self.assertIn('scarletImportInstallCertificate',XPC)
  self.assertIn('importInstallCertificate:reply:',GUEST)
  self.assertIn('timeout_state_unknown',HOST)
  self.assertNotIn('print(password)',GUEST)
if __name__=='__main__':unittest.main()
