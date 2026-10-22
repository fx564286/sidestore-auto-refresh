"""V65: separated App ID removal and free-team portal inventory refresh."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WIRE = (ROOT / "scripts/templates/v3_wire_contract.swift").read_text()
SERVICE = (ROOT / "scripts/templates/v3_sidestore_service.swift").read_text()
SHELL = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text()

class AppIDManagementTests(unittest.TestCase):
    def test_delete_is_a_mutation_and_not_read_only(self):
        operations = WIRE.split("static let operations: Set<String> =", 1)[1].split(
            "static let readOperations:", 1)[0]
        read_only = WIRE.split("static let readOperations: Set<String> =", 1)[1].split(
            "static func decodeRequest", 1)[0]
        self.assertIn('"devDeleteAppID"', operations)
        self.assertNotIn('"devDeleteAppID"', read_only)

    def test_delete_requires_current_apple_portal_record(self):
        self.assertIn('case "devDeleteAppID":', SERVICE)
        self.assertIn("ids.first(where: { $0.identifier == target })", SERVICE)
        self.assertIn("DeveloperPortalProxy.shared.deleteAppID(item, team: team)", SERVICE)
        self.assertIn("!bundle.hasPrefix(\"com.kdt.livecontainer\")", SERVICE)
        self.assertIn('!bundle.contains("sidestore")', SERVICE)
        self.assertIn('!bundle.contains("scarletcrystal")', SERVICE)
        self.assertNotIn('case "devResetQuota":', SERVICE)

    def test_ui_requires_confirmation_then_refreshes(self):
        self.assertIn('Section("Apple App IDs (\\(appIDs.count))")', SHELL)
        self.assertIn('"Apple 서버 등록 현황 새로고침"', SHELL)
        self.assertIn('Button("삭제", role: .destructive)', SHELL)
        self.assertIn('Button("삭제 확인", role: .destructive)', SHELL)
        self.assertIn('await deleteSelectedPortalAppID(selected)', SHELL)
        self.assertIn('await refreshPortalAppIDsAfterDelete()', SHELL)
        self.assertIn('operation: "devDeleteAppID"', SHELL)
        self.assertIn('operation: "devAppIDs"', SHELL)
        self.assertIn("7일 등록 한도", SHELL)
        self.assertIn("appIDLastChecked = Date()", SHELL)

    def test_delete_does_not_revoke_certificate_or_delete_app(self):
        region = SERVICE.split('case "devDeleteAppID":', 1)[1].split('case "devGroups":', 1)[0]
        self.assertNotIn("revokeCertificate", region)
        self.assertNotIn("deleteApplication", region)
        self.assertNotIn("addAppID", region)
        self.assertNotIn("createProvisioningProfile", region)

if __name__ == "__main__":
    unittest.main()
