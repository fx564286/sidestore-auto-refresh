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

SETTINGS_FIXTURE='''private extension SettingsViewController
{
    func signIn()
    {
        let result = try await AuthManager.shared.signIn(presentingViewController: self)
    }
}
'''

SCENE_FIXTURE='''final class SceneDelegate {
    func scene(_ scene: UIScene, willConnectTo session: UISceneSession, options connectionOptions: UIScene.ConnectionOptions)
    {
    }
    func sceneDidBecomeActive(_ scene: UIScene)
    {
        debugLog("[SceneDelegate] sceneDidBecomeActive() invoked")
    }
}
'''

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
        for marker in ('case "signin":','ScarletOriginalSideStoreSignIn.request()',
                       'SettingsViewController','AuthManager.shared.isAuthenticated',
                       'settings.scarletStartNativeAppleSignIn()', 'case "pairing":', 'case "install":'):
            self.assertIn(marker,out)
        self.assertIn('guard url.path.isEmpty || url.path == "/"',out)
        self.assertIn('originalTwoFactorUIUnmodified',Path(route.__file__).read_text())
        self.assertIn('guard pendingSignIn, open() else { return false }',out)
        scene=route.apply_scene(SCENE_FIXTURE)
        self.assertIn('ScarletOriginalSideStoreSignIn.activatePending()',scene)
        with self.assertRaises(RuntimeError):
            route.apply_scene(scene)
        with self.assertRaises(RuntimeError):
            route.apply(out)
        with self.assertRaises(RuntimeError):
            route.apply(UPSTREAM_FIXTURE.replace('case "install":','case "new-flow":'))

    def test_workflow_and_package_gate_must_include_original_login(self):
        self.assertIn('patch_sidestore_native_signin.py',WORKFLOW)
        self.assertIn('--side-auth-report artifacts/side/native-signin-adapter.json',WORKFLOW)
        self.assertIn('originalSideStoreAuthFlowPreserved',PACKAGER)
        self.assertIn('loginColdLaunchDeferralEnabled',PACKAGER)
        self.assertIn('"loginDeviceVerified":False',PACKAGER)
        self.assertIn('codesignedWithAppleProfile":False',PACKAGER)

    def test_settings_login_action_goes_direct_without_intermediate_page(self):
        ui=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
        settings=ui[ui.index("    private var settings: some View {"):ui.index("    private var connection: some View {")]
        self.assertIn('Text("Apple ID 로그인")',settings)
        self.assertIn('onAction(.serviceBeginSignIn)',settings)
        self.assertIn('SCARLET_SETTINGS_NATIVE_APPLE_LOGIN',settings)
        self.assertNotIn('Text("계정 및 서명 열기")',settings)
        self.assertIn('SCARLET_SIGNING_MANAGEMENT',settings)
        self.assertIn('showConnectionDetails = true',settings)
        self.assertIn('onAction(.serviceBeginSignIn)',settings)

    def test_no_credentials_or_2fa_captured_by_adapter(self):
        code=Path(route.__file__).read_text()
        self.assertNotIn('let password =',route.ADAPTER)
        self.assertNotIn('verificationCode(',route.ADAPTER)
        self.assertNotIn('Keychain.shared',route.ADAPTER)
        self.assertNotIn('AnisetteProvider.fetch',route.ADAPTER)
        self.assertNotIn('AuthManager.shared.signIn(',route.ADAPTER)
        self.assertIn('settings.scarletStartNativeAppleSignIn()',route.ADAPTER)
        self.assertNotIn('settings.signIn()',route.ADAPTER)
        patched=route.apply_settings(SETTINGS_FIXTURE)
        self.assertIn('func scarletStartNativeAppleSignIn()',patched)
        self.assertIn('AuthManager.shared.signIn(presentingViewController: self)',patched)
        with self.assertRaises(RuntimeError):
            route.apply_settings(patched)

if __name__=="__main__":
    unittest.main()
