"""P73: use native verified installed Scarlet app, never fabricate refresh receipts."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
E=(R/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
A=(R/'HostApp/ScarletAuthXPCSupport.swift').read_text()
B=(R/'HostApp/ScarletAutomaticRenewal.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class SideStoreEmbeddedHostBootstrap(unittest.TestCase):
 def test_original_db_skips_extension_but_bridge_uses_actual_executable_host(self):
  p=E.split('private actor ScarletGuestHostManagedBootstrap {',1)[1].split('// Runs inside the REAL embedded',1)[0]
  for marker in ('ProcessInfo.processInfo.arguments.first',
                 'Bundle(for: ScarletGuestRefreshAgent.self)',
                 'verifiedHostBundleURL(hostBundlePath: hostBundlePath)',
                 'directory.lastPathComponent == "LiveProcess.appex"',
                 'directory.deletingLastPathComponent().lastPathComponent == "PlugIns"',
                 'profile.expirationDate > Date()',
                 'profile.teamIdentifier == owner.teamID',
                 'ScarletInstallTeamAuthority.matchingCertificate(',
                 'CacheAppOperation.cachePayload(for: hostURL)',
                 'cachedHost.provisioningProfile?.teamIdentifier == currentTeamID'):
   self.assertIn(marker,p)
  self.assertNotIn('UserDefaults.standard.set(',p)
 def test_one_host_record_uses_original_sidestore_models_and_native_refresh(self):
  p=E.split('private actor ScarletGuestHostManagedBootstrap {',1)[1].split('// Runs inside the REAL embedded',1)[0]
  for marker in ('private var active: Task<String, Never>?',
                 'InstalledApp.first(satisfying: duplicate, in: context)',
                 '$0.isActiveTeam',
                 'InstalledApp(', 'record.team = team',
                 'record.isActive = true',
                 'record.useMainProfile = false',
                 'record.appBundleFingerprint = signature',
                 'InstalledExtension(', 'record.appExtensions = extensions',
                 'try context.save()',
                 'await context.perform { context.rollback() }'):
   self.assertIn(marker,p)
  self.assertEqual(E.count('ScarletGuestHostManagedBootstrap.shared.ensure(hostBundlePath: hostBundlePath)'),2)
  self.assertIn('AppManager.shared.backgroundRefresh(',E)
  self.assertIn('no_managed_apps_for_selected_team',E)
  self.assertIn('host_registration_failed',A)
  self.assertIn('case "host_registration_failed", "host_payload_cache_unavailable"',B)
 def test_release(self):
  for marker in ('fix/scarlet-v48-r6p73-native-managed-host-20261115',
                 '--host-build-version 3.8.73',
                 'Scarlet-Crystal-V48-R6P73-MANAGED-HOST-UNSIGNED.ipa',
                 'scarlet-v48-r6p73-native-managed-host-unsigned-20261115'):
   self.assertIn(marker,W)
if __name__=='__main__': unittest.main()
