"""V30 regression gates for SideStore Apple Team reconciliation.

Device report bb975c6f04dc: pairing_verified followed by native refresh
sidestore_auth_missing. Upstream SideStore PreflightChecksOperation needs an
active CoreData Team, while Scarlet's direct SideSign login saved only tokens.
These are source contracts; device signing/profile renewal needs readback.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SIGNIN = (ROOT / "integration/ScarletGuestSignInAgent.swift.txt").read_text()
REFRESH = (ROOT / "integration/ScarletGuestRefreshAgent.swift.txt").read_text()
XPC = (ROOT / "HostApp/ScarletAuthXPCSupport.swift").read_text()
GUIDE = (ROOT / "HostApp/ScarletAutomaticRenewal.swift").read_text()
WIRE = (ROOT / "integration/wire_scarlet_auth.py").read_text()
BUILD = (ROOT.parent / ".github/workflows/scarlet-paired-engines-build.yml").read_text()


class V30SideStoreTeamIntegration(unittest.TestCase):
    def test_original_signed_team_only_and_portal_verified(self):
        self.assertIn('let expectedTeamID = "P8EZT3U5N4"', SIGNIN)
        self.assertIn('DeveloperPortalProxy.shared.fetchTeams(', SIGNIN)
        self.assertIn('$0.identifier == expectedTeamID', SIGNIN)
        self.assertIn('return "sidestore_team_mismatch"', SIGNIN)
        self.assertNotIn('teams.first!', SIGNIN)
        self.assertNotIn('team = ALTTeam(identifier:', SIGNIN)

    def test_active_team_and_account_persisted_in_original_coredata(self):
        for fragment in (
            'try await DatabaseManager.shared.start()',
            'AuthManager.shared.getAuthenticatedTeam()',
            'DatabaseManager.shared.persistentContainer',
            'newBackgroundContext()', 'Account.first(satisfying:',
            'Team.first(satisfying:', 'Team(team, account: account, context: context)',
            'storedTeam.update(team: team)',
            'item.isActiveAccount = item.objectID == account.objectID',
            'item.isActiveTeam = item.objectID == storedTeam.objectID',
            'try context.save()', '"team_restored"',
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, SIGNIN)
        self.assertLess(SIGNIN.index('try context.save()'),
                        SIGNIN.index('let verified = try await AuthManager.shared.getAuthenticatedTeam()'))

    def test_login_ack_waits_for_team_and_uses_existing_token(self):
        self.assertIn('guard persistedState()', SIGNIN)
        self.assertIn('let teamState = await ensureActiveTeamForRefresh()', SIGNIN)
        self.assertIn('teamState == "ready" || teamState == "team_restored"', SIGNIN)
        self.assertLess(SIGNIN.index('let teamState = await ensureActiveTeamForRefresh()'),
                        SIGNIN.index('finish(id, code: 0, domain: "success")'))
        self.assertIn('forKey: "scarlet.auth.lastSuccessfulAnisetteProfile"', SIGNIN)

    def test_native_refresh_repairs_team_before_minimuxer_and_appmanager(self):
        self.assertIn('ScarletGuestSignInAgent', REFRESH)
        self.assertIn('.ensureActiveTeamForRefresh()', REFRESH)
        team = REFRESH.index('.ensureActiveTeamForRefresh()')
        minimuxer = REFRESH.index('ScarletGuestDeviceTransport.ensureReady()', team)
        operation = REFRESH.index('AppManager.shared.backgroundRefresh(', minimuxer)
        self.assertLess(team, minimuxer)
        self.assertLess(minimuxer, operation)
        self.assertIn('reply(false, teamState)', REFRESH)

    def test_specific_failure_categories_and_no_credential_leak(self):
        for reason in ('sidestore_team_mismatch', 'sidestore_team_recovery_failed'):
            self.assertIn('"' + reason + '"', SIGNIN)
            self.assertIn('"' + reason + '"', XPC)
            self.assertIn('case "' + reason + '"', GUIDE)
        for forbidden in ('clearSignInInfo(', 'revokeCertificate(', 'deleteApp(',
                          'savePairingFile(', 'NSLog(', 'print(email)'):
            self.assertNotIn(forbidden, SIGNIN)
        self.assertIn('ScarletGuestSignInAgent.swift.txt', WIRE)
        self.assertIn('ScarletGuestRefreshAgent.swift.txt', WIRE)

    def test_v30_branch_is_in_paired_engine_build_pipeline(self):
        self.assertIn('fix/scarlet-v30-restore-sidestore-active-team-20261110', BUILD)
        self.assertIn('cargo build --release --locked --target aarch64-apple-ios', BUILD)
        self.assertIn('package_paired.py', BUILD)


if __name__ == "__main__":
    unittest.main()
