"""P111 code-level regression: installed-host signed Team is authoritative.

These source-contract tests are not a signed iPhone install/rotation proof.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
READINESS = (ROOT / "rebuild/HostApp/ScarletSigningReadinessPanel.swift").read_text()
WORKER = (ROOT / "rebuild/integration/ScarletGuestRefreshAgent.swift.txt").read_text()
BASE = "com.kdt.livecontainer.P8EZT3U5N4"
FLOW = (ROOT / ".github/workflows/scarlet-paired-engines-build.yml").read_text()

def valid(team: str) -> bool:
    return len(team.encode()) == 10 and all(ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for ch in team)

def allowed_bundle(bundle: str, team: str) -> bool:
    return valid(team) and bundle in (BASE, BASE + "." + team)

class SignedHostTeamAuthority(unittest.TestCase):
    def test_signed_team_drives_host_runtime_readiness(self):
        inspect = READINESS.split("static func inspect()", 1)[1].split("var safeBlockCategory", 1)[0]
        self.assertIn("let teamID = team ??", inspect)
        self.assertIn("let validSignedTeam = teamID.utf8.count == 10", inspect)
        self.assertIn('baseBundleID + "." + teamID', inspect)
        self.assertIn("developerTeamEntitled: validSignedTeam", inspect)
        self.assertNotIn('developerTeamEntitled: team == "P8EZT3U5N4"', inspect)
        self.assertIn('applicationID == (team! + "." + bundleID!)', inspect)
        self.assertIn('let expectedGroup = "group.com.SideStore.SideStore." + (team ?? "")', inspect)
        self.assertIn("sideStoreAppGroupAccessible: accessible", inspect)

    def test_worker_source_and_registration_use_same_provisioning_team(self):
        source = WORKER.split("func verifiedInstalledHostID(", 1)[1].split("func verifiedSameTeamManualHostURL(", 1)[0]
        self.assertIn("let profileTeam = profile.teamIdentifier", source)
        self.assertIn("let validSignedTeam = profileTeam.utf8.count == 10", source)
        self.assertIn('id == baseID || id == baseID + "." + profileTeam', source)
        self.assertNotIn('id == "com.kdt.livecontainer.P8EZT3U5N4.P8EZT3U5N4"', source)
        self.assertIn("guard verifiedInstalledHostID(hostBundlePath: hostBundlePath) == bundleID", WORKER)

    def test_a_and_b_identities_and_invalid_suffixes(self):
        for team in ("P8EZT3U5N4", "JU2Z5J5ZSA"):
            self.assertTrue(allowed_bundle(BASE, team))
            self.assertTrue(allowed_bundle(BASE + "." + team, team))
            self.assertFalse(allowed_bundle(BASE + ".FOREIGN999", team))
        for team in ("", "short", "lowercase1", "JU2Z5J5ZSA-"):
            self.assertFalse(allowed_bundle(BASE, team))

    def test_p111_native_ci_identity_and_public_unsigned_release_route(self):
        for marker in ('fix/scarlet-v48-r6p111-rootcause-20261118',
                       '--host-build-version 3.8.111',
                       'if "r6p111" in __import__("os").environ.get("GITHUB_REF", ""): version="3.8.111"',
                       'Scarlet-Crystal-V48-R6P111-SIGNED-TEAM-UNSIGNED.ipa',
                       'scarlet-v48-r6p111-signed-team-unsigned-20261118'):
            self.assertIn(marker, FLOW)
        self.assertIn('github.ref == \'refs/heads/fix/scarlet-v48-r6p111-rootcause-20261118\'', FLOW)

    def test_host_cross_team_migration_remains_fail_closed_without_data_evidence(self):
        # A->B is NOT an in-place re-sign promise: original upstream
        # FetchProvisioningProfilesOperation may append B to the app ID.
        worker = WORKER.split("func verifiedSameTeamManualHostURL(", 1)[1]
        self.assertIn("profile.teamIdentifier == teamID", worker)
        self.assertIn("selectedTeamID == expectedOwner.teamID", WORKER)
        self.assertIn("activeSelectedSignerSerial(", WORKER)
        self.assertIn("AppManager.shared.install(.url(installedHost)", WORKER)
        self.assertIn("installed.resignedBundleIdentifier == currentHostID", WORKER)
        self.assertIn("installed, owner: expectedOwner", WORKER)

if __name__ == "__main__":
    unittest.main()
