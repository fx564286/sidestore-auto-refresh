"""The first-party login field is editable; requests fail closed if SideSign is not ready.

The real Apple authentication/2FA end-to-end path is NOT verified by source tests.
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
    def test_no_guest_signin_window_or_deeplink(self):
        self.assertIn("showScarletAppleIDLogin = true",HOST)
        self.assertIn("ScarletAppleIDLoginSheet(engine:",HOST)
        self.assertNotIn("LCUtils.openSideStore(",HOST)
        self.assertIn("prepareDeviceIPAInstall(selected)",HOST)
        self.assertNotIn("sidestore://signin",HOST)
        self.assertNotIn("openEmbeddedSideStore(signIn:",HOST)
        self.assertNotIn("patch_sidestore_native_signin.py",WORKFLOW)

    def test_login_secret_is_ephemeral_and_2fa_supported_in_ui(self):
        for marker in ("SCARLET_FIRST_PARTY_LOGIN_SHEET",
                       "SCARLET_APPLE_ID_FIELD","SCARLET_APPLE_PASSWORD_FIELD",
                       "SCARLET_2FA_CODE","SCARLET_OWN_LOGIN_SUBMIT",
                       "SecureField(","textContentType(.oneTimeCode)"):
            self.assertIn(marker,SHEET)
        for forbidden in ("UserDefaults.standard.set","appendingPathComponent",
                          "print(password)","sidestore://",".disabled(!engine.isReady)"):
            self.assertNotIn(forbidden,SHEET)
        self.assertIn('password = ""',SHEET)
        self.assertIn("guard transportReady && engine.isReady else {",SHEET)

    def test_real_bridge_is_present_but_device_auth_not_yet_verified(self):
        self.assertIn("protocol ScarletAppleSignInEngine",SHEET)
        self.assertIn("ScarletConnectedSideSignEngine()",HOST)
        self.assertIn("try await engine.prepare()",SHEET)
        self.assertNotIn("var isReady: Bool { false }",SHEET)
        self.assertNotIn("ScarletPendingSideStoreEngineBridge",HOST+SHEET)
        self.assertIn("--mode livecontainer",WORKFLOW)
        self.assertIn("--mode sidestore",WORKFLOW)
        self.assertIn('"sideStoreEngineTransportConnected":False',PACKAGER)
        self.assertIn('"loginDeviceVerified":False',PACKAGER)
        self.assertIn('"sideStoreAppleAuthenticationVerified":False',PACKAGER)
        self.assertIn("ScarletAppleIDLoginSheet.swift",INTEGRATOR)

    def test_settings_tab_direct_account_entry(self):
        self.assertIn("if selected == .settings {",UI)
        self.assertIn("case .serviceBeginSignIn:",HOST)
        self.assertIn("SCARLET_SETTINGS_NATIVE_APPLE_LOGIN",INTEGRATOR)
        self.assertIn("ScarletDiagnosticLogView()",INTEGRATOR)
        self.assertIn("nativeSettings()",UI)
        self.assertIn("SCARLET_INLINE_NATIVE_LC_SETTINGS",UI)
        self.assertNotIn("showConnectionDetails",UI)

if __name__=="__main__":
    unittest.main()
