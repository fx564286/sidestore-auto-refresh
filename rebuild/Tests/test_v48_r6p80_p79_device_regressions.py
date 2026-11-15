"""P80 repairs only measured signed-P79 failures without changing account teams."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
G=(R/'integration/apply_scarlet_host.py').read_text()
H=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
C=(R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text()
GL=(R/'HostApp/ScarletNativeGlass.swift').read_text()
WF=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class P80NativeSignedDevice(unittest.TestCase):
 def test_original_archive_zero_is_not_assumed_complete(self):
  start=G.index('silent_success_anchor =')
  end=G.index('# Tiny synthetic upstream test fixtures',start)
  part=G[start:end]
  for token in ('scarletQueuedIPAURL != nil',
       'before.contains(where: { $0.hasSuffix(".app") })',
       'scarletExtractGuestIPAFromMappedData(',
       '"native_archive_payload_invalid"',
       'throw NSError(domain: "ScarletGuestArchive", code: 80',
       '"mapped_archive_payload_recovered"'):
   self.assertIn(token,part,token)
  self.assertNotIn('removeItem(at: outputFolder)',part)
  self.assertNotIn('SecItemDelete',part)
 def test_p79_worse_island_rollback_restores_only_owned_same_size_header(self):
  part=C.split('// R6P54_OWNER_LAYOUT_CONTRACT_BEGIN')[1].split('// R6P54_OWNER_LAYOUT_CONTRACT_END')[0]
  for token in ('"original_frame"','originalSize=isfinite(desired.origin.y)',
                'vc && vc.view==par && w && par.window==w',
                'CGAffineTransformIsIdentity(head.transform)',
                'fabs(actual.size.width-desired.size.width)<2',
                'head.frame=desired;',
                'object_setClass(vc,original)',
                '[native.view setNeedsLayout];',
                '[native.view layoutIfNeeded];',
                '@"guest_original_owner_layout_restored"'):
   self.assertIn(token,part,token)
  for token in ('window.frame=','root.transform=', 'root.additionalSafeAreaInsets=',
                'scroll.contentOffset=', 'scroll.contentInset='):
   self.assertNotIn(token,part)
 def test_native_settings_in_form_not_title_overlay(self):
  self.assertNotIn('LCSettingsView()\n                        .safeAreaInset(edge: .top)',H)
  self.assertIn('LCSettingsView()\n                        // P80:',H)
  self.assertIn('Notification.Name("ScarletOpenNativeManagedApps")',H)
  self.assertIn('showManagedSlotSheet = true',H)
  sec=G.split('new_section="""',1)[1].split('if !scarletSavedAccounts.isEmpty',1)[0]
  self.assertIn('Toggle("실험적 전체화면 RAM 유지", isOn: $scarletResidentPilotEnabled)',sec)
  self.assertIn('"ScarletOpenNativeManagedApps"',sec)
  self.assertIn('SCARLET_NATIVE_SLOT_MANAGER_OPEN',sec)
  self.assertIn('@AppStorage("Scarlet.Feature.FullscreenResidentPilot.V45")',G)
  self.assertIn('contentMargins(.bottom, 56, for: .scrollContent)',GL)
 def test_team_and_guest_data_paths_preserved(self):
  self.assertIn('settings_account_switch_verified',G)
  self.assertIn('ScarletNativeSavedAccounts.activate(id)',G)
  self.assertIn('scarletGuestImportSignFailed',G)
  self.assertNotIn('removeCertificate()',H)
 def test_p80_native_release(self):
  for token in ('fix/scarlet-v48-r6p80-device-import-settings-island-20261116',
                '--host-build-version 3.8.80',
                '"r6p80"',
                'Scarlet-Crystal-V48-R6P80-DEVICE-FIXES-UNSIGNED.ipa',
                'scarlet-v48-r6p80-device-fixes-unsigned-20261116'):
   self.assertIn(token,WF)
if __name__=='__main__': unittest.main()
