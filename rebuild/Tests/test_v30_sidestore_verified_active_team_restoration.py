"""V30: V29 signed-device pairing succeeds; SideStore native refresh still
returned sidestore_auth_missing because Scarlet's custom Apple ID flow saved
tokens but did not invoke original SignInOperation.saveTeamAndAccount(makeActive).

The recovery must be Apple-portal verified and strictly bound to the TEAM in
the actual installed mobileprovision, never guessed from app bundle names,
stored cert OU, or an unrelated Apple account. User credentials, guest apps,
profiles, certificates, pairing and VPN must not be reset.
"""
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RESTORE=(ROOT/"integration/ScarletGuestAuthTeamRepair.swift.txt").read_text()
WIRE=(ROOT/"integration/wire_scarlet_auth.py").read_text()
AGENT=(ROOT/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()
XPC=(ROOT/"HostApp/ScarletAuthXPCSupport.swift").read_text()
AUTO=(ROOT/"HostApp/ScarletAutomaticRenewal.swift").read_text()
PANEL=(ROOT/"HostApp/ScarletSigningReadinessPanel.swift").read_text()
PAIR=(ROOT/"HostApp/ScarletNativeDevicePairing.swift").read_text()
GLASS=(ROOT/"HostApp/ScarletFullscreenGuestTab.swift").read_text()

class V30RestoreMissingTeam(unittest.TestCase):
    def test_existing_login_tokens_must_exist_without_fabrication(self):
        for line in ("auth.currentAppleID", "auth.adsid", "auth.xcodeToken"):
            self.assertIn(line,RESTORE)
        self.assertIn('return "sidestore_auth_token_missing"',RESTORE)
        self.assertNotIn("signIn(appleID:",RESTORE)
        self.assertNotIn("setActiveCertificate(",RESTORE)
        self.assertNotIn("clearSignInInfo(",RESTORE)

    def test_apple_confirmed_team_matches_signed_host_profile(self):
        for line in ("embedded.mobileprovision", "ALTProvisioningProfile(",
                     "profile.teamIdentifier", "DeveloperPortalProxy.shared.fetchTeams",
                     "portalTeams.filter", "$0.identifier == expectedTeamID"):
            self.assertIn(line,RESTORE)
        self.assertIn("matches.count == 1",RESTORE)
        self.assertIn('return "sidestore_auth_team_mismatch"',RESTORE)
        self.assertNotIn("teams[0]",RESTORE)
        self.assertNotIn("StoreApp.altstoreAppID +",RESTORE)

    def test_original_coredata_account_and_team_are_saved_non_destructively(self):
        self.assertIn("DatabaseManager.shared.start()",RESTORE)
        self.assertIn("db.activeTeam(in: context)",RESTORE)
        self.assertIn('if existingTeam != nil { return "auth_team_ready" }',RESTORE)
        self.assertIn("Account.first(satisfying:",RESTORE)
        self.assertIn("Team.first(satisfying:",RESTORE)
        self.assertIn("Account(ALTAccount(",RESTORE)
        self.assertIn("team = Team(verifiedTeam,",RESTORE)
        self.assertIn("account.isActiveAccount = true",RESTORE)
        self.assertIn("team.isActiveTeam = true",RESTORE)
        self.assertIn("try context.save()",RESTORE)
        self.assertIn("auth.getAuthenticatedTeam()",RESTORE)
        self.assertNotIn("removePersistentStore",RESTORE)
        self.assertNotIn("revokeCertificate(",RESTORE)

    def test_native_refresh_preflight_checks_signed_team_not_only_cert(self):
        self.assertIn("ScarletGuestAuthTeamRepair.swift.txt",WIRE)
        self.assertIn("ScarletGuestAuthTeamRepair.ensure()",AGENT)
        self.assertIn('"ready_auth_team_restored"',AGENT)
        self.assertIn('authState == "auth_team_ready"',AGENT)
        self.assertLess(AGENT.index('let authState = await ScarletGuestAuthTeamRepair.ensure()'),
                        AGENT.index("AppManager.shared.backgroundRefresh("))
        self.assertIn('reason == "ready_auth_team_restored"',XPC)
        self.assertIn('sidestore_auth_team_mismatch',XPC)
        self.assertIn('sidestore_auth_team_lookup_failed',XPC)
        self.assertIn('sidestore_auth_token_missing',XPC)
        self.assertIn('sidestore_auth_token_missing',AUTO)
        self.assertIn('ScarletNativeRefreshExecutor.execute()',PANEL)

    def test_pairing_and_native_glass_preserved(self):
        self.assertIn("stikpair_run_host(",PAIR)
        self.assertIn("pairing_saved_and_transport_ready",XPC)
        self.assertIn("glassPlate(radius: isOpen ? 28 : 31)",GLASS)
        self.assertIn("glass_morph_opened",GLASS)
        self.assertNotIn("deleteApp(",RESTORE)

if __name__=="__main__":
    unittest.main()
