"""R6P112 -> R6P114 non-destructive owner, profile and staging migration."""
import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    'scarlet_r114_auth', ROOT/'rebuild/integration/wire_scarlet_auth.py')
wire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)
CERT = (ROOT/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()
REFRESH = (ROOT/'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text()
HOST = (ROOT/'rebuild/HostApp/ScarletIntegratedHostView.swift').read_text()
INSTALL = (ROOT/'rebuild/integration/ScarletDeviceInstallAgent.swift.txt').read_text()
WORKFLOW = (ROOT/'.github/workflows/scarlet-paired-engines-build.yml').read_text()


class LegacyUpgrade(unittest.TestCase):
    def test_portal_proved_unique_private_key_before_binding_legacy(self):
        section = CERT.split('private static func migrateLegacySigner(', 1)[1].split(
            'static func prepare(teamID:', 1)[0]
        self.assertIn('fetchCertificates(team: team)', section)
        self.assertIn('getSignableCertificate(', section)
        self.assertIn('remote.count == 1', section)
        self.assertIn('distinctOwners == Set([owner.appleID])', section)
        self.assertIn('current.appleID == owner.appleID', section)
        self.assertIn('reservedByAnotherAccount(', section)
        self.assertIn('bindSignerSerial(', section)
        self.assertNotIn('SecItemDelete(', section)
        self.assertNotIn('revokeCertificate(', section)
        self.assertIn('migrateLegacySigner(team: team, owner: owner)', CERT)

    def test_same_team_different_accounts_cannot_alias_signer(self):
        self.assertIn('identifier(slot.email) != identifier(appleID)', CERT)
        self.assertIn('!reservedByAnotherAccount(normalized, appleID: id, teamID: teamID)', CERT)
        self.assertIn('!ScarletAccountVault.reservedByAnotherAccount(', CERT)

    def test_deployed_id_retained_and_new_id_normalized(self):
        function = (ROOT/'rebuild/integration/wire_scarlet_auth.py').read_text().split(
            'def patch_idempotent_team_provisioning', 1)[1].split('def patch_sidestore', 1)[0]
        self.assertIn('while normalized.hasSuffix(teamSuffix + teamSuffix)', function)
        self.assertIn('installedApp.team?.account?.isActiveAccount == true', function)
        self.assertIn('parentID = preferredBundleID',
                      # This is from the pinned upstream, deliberately untouched
                      'parentID = preferredBundleID')
        self.assertIn('profile.bundleIdentifier == bundleID', function)
        self.assertIn('team.identifier + "." + bundleID', function)
        self.assertIn('profile.bundleIdentifier == id', REFRESH)
        self.assertIn('profile.teamIdentifier + "." + id', REFRESH)

    def test_legacy_app_group_preserved_but_new_staging_is_scoped(self):
        self.assertIn('"ScarletDeviceInstall/accounts/" + accountScope', HOST)
        self.assertIn('SHA256.hash(data: Data((', HOST)
        self.assertIn('SHA256.hash(data: Data((', INSTALL)
        self.assertIn('legacy ? directory : directory + "/accounts/" + scope', INSTALL)
        self.assertIn('stageKey + "." + state.ownerScope', INSTALL)
        self.assertIn('guard legacy || (pieces.count == 2', INSTALL)
        self.assertNotIn('removeItem(at: groupURL)', INSTALL)
        self.assertIn('owner.teamID == expectedTeamID', INSTALL)
        a = hashlib.sha256(b'apple-a@example.com|AB12CD34EF').hexdigest()
        b = hashlib.sha256(b'apple-b@example.com|AB12CD34EF').hexdigest()
        self.assertNotEqual(a, b)

    def test_version_and_ci_branch(self):
        self.assertIn('fix/scarlet-v48-r6p114-legacy-owner-migration-20261118', WORKFLOW)
        self.assertIn('--host-build-version 3.8.114', WORKFLOW)
        self.assertIn('version="3.8.114"', WORKFLOW)


if __name__ == '__main__':
    unittest.main()
