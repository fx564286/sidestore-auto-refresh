"""P85 signed-host origin authority, SideStore Team isolation, account cell divider."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
A=(R/'HostApp/ScarletAuthXPCSupport.swift').read_text()
G=(R/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
W=(R/'integration/wire_scarlet_auth.py').read_text()
S=(R/'integration/apply_scarlet_host.py').read_text()
WF=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class P85OriginPathAndSettings(unittest.TestCase):
 def test_host_origin_bundled_path_passed_to_both_workers(self):
  self.assertIn('client.scarletRefreshReadiness(Bundle.main.bundleURL.path)',A)
  self.assertIn('client.scarletPerformNativeRefresh(',A)
  self.assertIn('client.scarletPerformManualNativeRefresh(',A)
  self.assertIn('Bundle.main.bundleURL.path, reply: finished',A)
  for x in ('scarletRefreshReadiness:(NSString*)hostBundlePath reply:',
            'scarletPerformNativeRefresh:(NSString*)hostBundlePath reply:',
            'inspectHostBundle:reply:', 'performHostBundle:reply:'):
   self.assertIn(x,W)
  self.assertIn('inspectHostBundle(_ hostBundlePath: String',G)
  self.assertIn('performHostBundle(_ hostBundlePath: String',G)
  self.assertEqual(G.count('shared.ensure(hostBundlePath: hostBundlePath)'),2)
 def test_preserves_verified_existing_signed_host_team_and_cache(self):
  part=G.split('private actor ScarletGuestHostManagedBootstrap',1)[1].split('// Runs inside the REAL',1)[0]
  for x in ('hostBundlePath.hasPrefix("/")','resolvingSymlinksInPath()',
            '"PlugIns/LiveProcess.appex"','"embedded.mobileprovision"',
            'hostURL.pathExtension == "app"','ALTApplication(fileURL: hostURL)',
            'profile.expirationDate > Date()',
            'profile.teamIdentifier == owner.teamID',
            'matchingCertificate(', 'CacheAppOperation.cachePayload(for: hostURL)',
            'record.useMainProfile = false','record.appExtensions = extensions',
            'try context.save()'):
   self.assertIn(x,part,x)
  for forbidden in ('SecItemDelete','revokeCertificate','removeItem(at: hostURL)',
                    'Bundle.main.bundleURL'):  # guest cannot use its Bundle.main
   # allow comments discussing Bundle.main, not executable guest code
   body='\n'.join(x for x in part.splitlines() if not x.lstrip().startswith('//'))
   self.assertNotIn(forbidden,body)
 def test_account_rows_have_native_list_cell_without_broken_separator(self):
  sec=S.split('Section {\n                    if !scarletSavedAccounts.isEmpty',1)[1].split('} header: {\n                    Text("계정")',1)[0]
  self.assertNotIn('VStack(alignment: .leading, spacing: 10)',sec)
  self.assertIn('.buttonStyle(.plain)',sec)
  self.assertNotIn('.listRowSeparator(.hidden)',sec)
  self.assertIn('ForEach(scarletSavedAccounts)',sec)
  self.assertNotIn('Divider()',sec)
  self.assertIn('SCARLET_SETTINGS_SAVED_ACCOUNT_ROW',sec)
  self.assertIn('SCARLET_SETTINGS_ACTIVE_APPLE_ID',sec)
  self.assertIn('SCARLET_SETTINGS_SWITCH_APPLE_ID',sec)
  self.assertIn('ScarletNativeSavedAccounts.activate(id)',S)
 def test_original_guest_and_signing_unchanged(self):
  self.assertIn('guest_owner_layout_contract',
        (R/'integration/ScarletGuestIslandContentGuard.m.txt').read_text())
  self.assertIn('SCARLET_SETTINGS_ADD_LOGIN',S)
  self.assertIn('scarletGuestImportSignFailed',S)
 def test_version_release_and_ci(self):
  for x in ('fix/scarlet-v48-r6p85-host-origin-refresh-settings-20261116',
      '3.8.85','"r6p85"','Scarlet-Crystal-V48-R6P85-REFRESH-ACCOUNT-UNSIGNED.ipa',
      'scarlet-v48-r6p85-refresh-account-unsigned-20261116'):
   self.assertIn(x,WF)
  release=next(x for x in WF.splitlines() if x.strip().startswith("if: github.event_name == 'push'") and 'refs/heads' in x)
  self.assertIn('refs/heads/fix/scarlet-v48-r6p85-host-origin-refresh-settings-20261116',release)
if __name__=='__main__':unittest.main()
