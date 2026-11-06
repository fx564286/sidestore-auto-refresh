"""Source-level login route acceptance. Never assert real Apple account success."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
WORKFLOW=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
PACKAGER=(ROOT/"integration/package_paired.py").read_text()
sys.path.insert(0,str(ROOT/"integration"))
import patch_sidestore_native_signin as route

UPSTREAM_FIXTURE='''@MainActor
class URLHandler {
    func handle(_ url: URL) -> Bool {
        guard let components = URLComponents(url: url, resolvingAgainstBaseURL: false) else { return false }
        switch components.host {
        case "pairing":
            return true
        case "install":
            return true
        default:
            return false
        }
    }
}
'''

class NativeSideStoreLoginRoute(unittest.TestCase):
    def test_login_action_goes_to_original_side_store_signin_not_home(self):
        self.assertIn('case .serviceBeginSignIn:\n            openEmbeddedSideStore(signIn: true)',HOST)
        self.assertIn('urlStr: signIn ? "sidestore://signin" : nil',HOST)
        self.assertIn('LCUtils.openSideStore(',HOST)
        self.assertNotIn('AuthManager.shared.signIn(',HOST)
        self.assertNotIn('Keychain.shared',HOST)
        self.assertNotIn('appleIDPassword',HOST)

    def test_native_route_has_pinned_and_fail_closed_contract(self):
        out=route.apply(UPSTREAM_FIXTURE)
        for marker in ('case "signin":','ScarletOriginalSideStoreSignIn.open()',
                       'SettingsViewController','AuthManager.shared.isAuthenticated',
                       'settings.signIn()', 'case "pairing":', 'case "install":'):
            self.assertIn(marker,out)
        self.assertIn('guard url.path.isEmpty || url.path == "/"',out)
        self.assertIn('originalTwoFactorUIUnmodified',Path(route.__file__).read_text())
        with self.assertRaises(RuntimeError):
            route.apply(out)
        with self.assertRaises(RuntimeError):
            route.apply(UPSTREAM_FIXTURE.replace('case "install":','case "new-flow":'))

    def test_workflow_and_package_gate_must_include_original_login(self):
        self.assertIn('patch_sidestore_native_signin.py',WORKFLOW)
        self.assertIn('--side-auth-report artifacts/side/native-signin-adapter.json',WORKFLOW)
        self.assertIn('originalSideStoreAuthFlowPreserved',PACKAGER)
        self.assertIn('"loginDeviceVerified":False',PACKAGER)
        self.assertIn('codesignedWithAppleProfile":False',PACKAGER)

    def test_no_credentials_or_2fa_captured_by_adapter(self):
        code=Path(route.__file__).read_text()
        self.assertNotIn('let password =',route.ADAPTER)
        self.assertNotIn('verificationCode(',route.ADAPTER)
        self.assertNotIn('Keychain.shared',route.ADAPTER)
        self.assertNotIn('AnisetteProvider.fetch',route.ADAPTER)
        self.assertNotIn('AuthManager.shared.signIn(',route.ADAPTER)
        self.assertIn('settings.signIn()',route.ADAPTER)

if __name__=="__main__":
    unittest.main()
