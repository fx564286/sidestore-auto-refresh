"""V96: UI->wire->portal profile deletion; no device removal or App ID mutation."""
from pathlib import Path
import os
import unittest

ROOT=Path(__file__).resolve().parents[1]
T=ROOT/"scripts"/"templates"

class ExtensionProfileControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.headless=(T/"v3_headless_runtime.swift").read_text()
        cls.service=(T/"v3_sidestore_service.swift").read_text()
        cls.wire=(T/"v3_wire_contract.swift").read_text()
        cls.ui=(T/"v3_unified_shell.swift").read_text()

    def test_typed_portal_profile_ids_not_mirror_optional_strings(self):
        fn=self.headless.split("static func profileRow(",1)[1].split("static func developerProfiles()",1)[0]
        self.assertIn('profile.provisioningProfileId ?? ""',fn)
        self.assertIn('"bundleID": profile.bundleIdentifier ?? ""',fn)
        self.assertIn('"expiration": profile.dateExpire',fn)
        self.assertNotIn('Mirror(reflecting:',fn)

    def test_mutation_is_not_read_only_and_is_exactly_allowlisted(self):
        self.assertIn('"devDeleteExtensionProfile"',self.wire)
        wire=self.wire.split('static let readOperations:',1)[1].split('static func decodeRequest',1)[0]
        self.assertNotIn('"devDeleteExtensionProfile"',wire)
        self.assertIn('case "devDeleteExtensionProfile":',self.service)
        self.assertIn('case "devTeams", "devDevices", "devAppIDs", "devDeleteAppID", "devDeleteExtensionProfile"',self.service)

    def test_portal_scope_protection_and_server_confirmation(self):
        code=self.service.split('case "devDeleteExtensionProfile":',1)[1].split('case "sourcePreview":',1)[0]
        for must in [
            '$0.provisioningProfileId == target',
            'profile.bundleIdentifier?.lowercased()',
            '".shareextension"', '".altwidget"', '".liveprocess"', '".launchappextension"',
            'getAuthenticatedTeam()).identifier == team.identifier',
            'DeveloperPortalProxy.shared.deleteProvisioningProfile(',
            'DeveloperPortalProxy.shared.listProvisioningProfiles(team: team)',
            'remaining.contains(where: { $0.provisioningProfileId == target })',
            '"verifiedAbsent": true',
            '"scope": "apple_portal_only"']:
            self.assertIn(must,code)
        for forbidden in ['removeProvisioningProfile(', 'deleteAppID(', 'deleteCertificate(', 'deleteApp(', 'removeInstalledApp(', 'try!']:
            self.assertNotIn(forbidden,code)

    def test_ui_requires_explicit_selection_confirmation(self):
        ui=self.ui.split('struct V3DeveloperServicesView: View {',1)[1].split('struct V3FilePicker:',1)[0]
        for must in ['profileDeleteTarget = row', 'showProfileDeleteConfirmation = true',
                     '.alert("확장 프로파일 삭제"', 'Button("Apple 서버에서 삭제", role: .destructive)',
                     'operation: "devDeleteExtensionProfile", target: identifier',
                     'V3ServiceBridge.strictBool(response["verifiedAbsent"]) == true',
                     'operation: "devProfiles"', 'profileLastChecked = Date()']:
            self.assertIn(must,ui)
        self.assertIn('!rows.contains(where: { ($0["identifier"] as? String) == identifier })',ui)
        self.assertIn('기기 설치 프로파일과 앱은 그대로',ui)

    def test_optional_generated_swift(self):
        root=os.getenv('SIDESTORE_TEST_SOURCE')
        if not root or os.getenv('V96_PATCHED_SIDESTORE')!='1':
            return
        generated=Path(root)
        files=list(generated.rglob('*.swift'))
        self.assertTrue(any('case "devDeleteExtensionProfile":' in f.read_text(errors='replace') for f in files))
        self.assertTrue(any('profile.provisioningProfileId ?? ""' in f.read_text(errors='replace') for f in files))

if __name__=="__main__":
    unittest.main()
