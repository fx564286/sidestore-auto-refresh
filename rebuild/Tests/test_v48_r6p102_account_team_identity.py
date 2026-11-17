"""P102 owner-specific account recovery; static contracts, iPhone remains authoritative."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
LOGIN = (ROOT / "rebuild/integration/ScarletGuestSignInAgent.swift.txt").read_text()
NATIVE = (ROOT / "rebuild/integration/ScarletGuestSavedAccounts.swift.txt").read_text()
HOST = (ROOT / "rebuild/HostApp/ScarletAuthXPCSupport.swift").read_text()
SETTINGS = (ROOT / "rebuild/integration/apply_scarlet_host.py").read_text()
SHEET = (ROOT / "rebuild/HostApp/ScarletAppleIDLoginSheet.swift").read_text()
MODEL = Path("/workspace/scarlet-r6p73-sidestore-source/AltStore/Core/Model/AltStore.xcdatamodeld/AltStore 17_7.xcdatamodel/contents")

class AccountIdentityAndOwnership(unittest.TestCase):
    def test_recovery_does_not_overwrite_another_apple_id_record(self):
        recovery = LOGIN.split("static func ensureActiveTeamForRefresh(", 1)[1].split(
            "@objc(begin:)", 1)[0]
        self.assertIn("existing.appleID.caseInsensitiveCompare(email)", recovery)
        self.assertIn("ScarletAccountTeamOwnershipCollision.accountIdentifier", recovery)
        self.assertIn("existing.account?.objectID == account.objectID", recovery)
        self.assertIn("ScarletAccountTeamOwnershipCollision.teamIdentifier", recovery)
        self.assertIn("confirmedOwner?.appleID.caseInsensitiveCompare(email)", recovery)
        self.assertIn('return "sidestore_team_identifier_collision"', recovery)
        # False-positive binding to a globally unique Team identifier must be vetoed.
        self.assertLess(recovery.index("existing.account?.objectID == account.objectID"),
                        recovery.index("storedTeam.update(team: team)"))
        self.assertNotIn("account.appleID = email", recovery)

    def test_switch_validates_keychain_and_coredata_account_together(self):
        activated = NATIVE.split("static func activate(_ slot:", 1)[1].split(
            "static func savedRows()", 1)[0]
        for token in (
            "auth.currentAppleID?.trimmingCharacters(",
            "auth.adsid == slot.adsid",
            "auth.xcodeToken == slot.xcodeToken",
            "ScarletInstallTeamAuthority.activeOwnership()",
            "owner.appleID == identifier(slot.email)",
            "owner.teamID == slot.teamID",
        ):
            self.assertIn(token, activated)

    def test_account_list_reports_actual_per_owner_managed_apps(self):
        rows = NATIVE.split("static func savedRows()", 1)[1].split(
            "static func switchTo", 1)[0]
        self.assertIn("context.fetch(Team.fetchRequest())", rows)
        self.assertIn("context.fetch(InstalledApp.fetchRequest())", rows)
        self.assertIn("email.trimmingCharacters(", rows)
        self.assertIn("ownerKeys: Set<String>", rows)
        self.assertIn("ownerVerified: verifiedOwner", rows)
        self.assertIn("managedAppCount: min(999,", rows)
        self.assertIn("verifiedOwner && (", rows)
        self.assertIn("for: slot.teamID, appleID: slot.email", rows)
        for key in ("ownerVerified: Bool", "managedAppCount: Int"):
            self.assertIn(key, HOST)

    def test_settings_rebinds_exact_apple_id_and_team_not_just_team(self):
        self.assertIn("let accountID = active[0].id", SETTINGS)
        self.assertIn("$0.id == accountID && $0.teamID == teamID", SETTINGS)
        self.assertIn("$0.id == id && $0.active &&", SETTINGS)
        self.assertIn("$0.teamID == expectedTeam && $0.ownerVerified", SETTINGS)
        self.assertIn('Text("팀 " + row.teamID)', SETTINGS)
        self.assertIn('String(row.managedAppCount)', SETTINGS)
        self.assertIn('Text("팀 " + slot.teamID)', SHEET)
        self.assertIn('String(slot.managedAppCount)', SHEET)
        self.assertNotIn("SecItemDelete(", NATIVE)
        self.assertNotIn("revokeCertificate(", NATIVE)

    def test_database_schema_uniqueness_invariant_is_declared(self):
        if not MODEL.exists():
            self.skipTest("Upstream SideStore model not mounted; source guards still checked")
        import xml.etree.ElementTree as ET
        root = ET.parse(MODEL).getroot()
        for name in ("Account", "Team"):
            entity = next(e for e in root.findall(".//entity")
                          if e.attrib.get("name") == name)
            constraints = {v.attrib.get("value") for v in
                           entity.findall("./uniquenessConstraints/uniquenessConstraint/constraint")}
            self.assertIn("identifier", constraints)

if __name__ == "__main__":
    unittest.main()
