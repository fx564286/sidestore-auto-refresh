"""Scarlet owns the Apple ID UI; SideStore guest login navigation is prohibited.

All assertions are source-level. Successful authentication requires a real
engine bridge and a signed device test; do not claim these based on CI.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
SHEET=(ROOT/"HostApp/ScarletAppleIDLoginSheet.swift").read_text()
WORKFLOW=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
PACKAGER=(ROOT/"integration/package_paired.py").read_text()
INTEGRATOR=(ROOT/"integration/apply_scarlet_host.py").read_text()
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()

class NativeScarletLoginContract(unittest.TestCase):
    def test_no_guest_signin_window_or_signin_deeplink(self):
        self.assertIn("showScarletAppleIDLogin = true",HOST)
        self.assertIn("ScarletAppleIDLoginSheet(engine:",HOST)
        self.assertNotIn("LCUtils.openSideStore(",HOST)
        self.assertIn("prepareDeviceIPAInstall()",HOST)
        self.assertNotIn("sidestore://signin",HOST)
        self.assertNotIn('onAction(.localOpenEmbeddedSideStore)',UI)
        self.assertNotIn('ScarletActionRow(title: "SideStore 열기"',UI)
        self.assertNotIn("openEmbeddedSideStore(signIn:",HOST)
        self.assertNotIn("patch_sidestore_native_signin.py",WORKFLOW)

    def test_login_ui_is_first_party_and_secret_redaction(self):
        for marker in ("SCARLET_FIRST_PARTY_LOGIN_SHEET",
                       "SCARLET_APPLE_ID_FIELD","SCARLET_APPLE_PASSWORD_FIELD",
                       "SCARLET_2FA_CODE","SCARLET_OWN_LOGIN_SUBMIT",
                       "SecureField(","textContentType(.oneTimeCode)"):
            self.assertIn(marker,SHEET)
        self.assertNotIn("UserDefaults.standard.set",SHEET)
        self.assertNotIn("appendingPathComponent",SHEET)
        self.assertNotIn("print(password)",SHEET)
        self.assertNotIn("sidestore://",SHEET)
        self.assertIn("password = \"\"",SHEET)

    def test_fail_closed_until_real_engine_transport(self):
        self.assertIn("protocol ScarletAppleSignInEngine",SHEET)
        self.assertIn("var isReady: Bool { false }",SHEET)
        self.assertIn("throw ScarletSignInBridgeError.engineNotConnected",SHEET)
        self.assertIn('"sideStoreEngineTransportConnected":False',PACKAGER)
        self.assertIn('"loginDeviceVerified":False',PACKAGER)
        self.assertIn('"sideStoreAppleAuthenticationVerified":False',PACKAGER)
        self.assertIn("ScarletAppleIDLoginSheet.swift",INTEGRATOR)

    def test_settings_direct_entry_unchanged(self):
        settings=UI[UI.index("    private var settings: some View {"):
                    UI.index("    private var connection: some View {")]
        self.assertIn('Text("Apple ID 로그인")',settings)
        self.assertIn("onAction(.serviceBeginSignIn)",settings)
        self.assertIn("SCARLET_SETTINGS_NATIVE_APPLE_LOGIN",settings)
        self.assertNotIn("계정 및 서명 열기",settings)

if __name__=="__main__":
    unittest.main()
