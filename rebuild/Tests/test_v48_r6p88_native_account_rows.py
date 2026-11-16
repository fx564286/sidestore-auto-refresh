"""P88: native one-row-per-account and visually stable action state."""
from pathlib import Path
import unittest
S=(Path(__file__).resolve().parents[1]/'integration/apply_scarlet_host.py').read_text()
class P88NativeRows(unittest.TestCase):
 def test_rows_not_embedded_in_a_vstack_form_cell(self):
  body=S.split('Section {\n                    if !scarletSavedAccounts.isEmpty',1)[1].split('} header: {\n                    Text("계정")',1)[0]
  self.assertIn('ForEach(scarletSavedAccounts) { row in',body)
  self.assertIn('Button {',body)
  self.assertNotIn('VStack(alignment: .leading, spacing: 10)',body)
  self.assertIn('.buttonStyle(.plain)',body)
  self.assertNotIn('.listRowSeparator(.hidden)',body)
  self.assertNotIn('Divider()',body)
  self.assertIn('SCARLET_SETTINGS_SAVED_ACCOUNT_ROW',body)
 def test_add_login_does_not_flash_disabled_tint(self):
  body=S.split('if let scarletAccountSwitchError',1)[1].split('SCARLET_NATIVE_DIAGNOSTICS_ENTRY',1)[0]
  self.assertIn('SCARLET_SETTINGS_ADD_LOGIN',body)
  self.assertIn('.allowsHitTesting(scarletSwitchingAccountID == nil',body)
  self.assertNotIn('.disabled(scarletSwitchingAccountID',body)
  self.assertIn('"추가 로그인"',body)
 def test_switch_button_no_progress_label_swap(self):
  body=S.split('ForEach(scarletSavedAccounts) { row in',1)[1].split('} else if scarletLoginVerified == true',1)[0]
  self.assertIn('Text("전환")',body)
  self.assertNotIn('ProgressView()',body)
if __name__=='__main__':unittest.main()
