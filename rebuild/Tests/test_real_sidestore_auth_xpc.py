"""Static contract for the SideStore guest-auth XPC adapter.

These tests do not prove that a physical iPhone can reach Apple; the paired
engine archive and real device authentication remain separate release gates.
"""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def read(path):
    return (ROOT/path).read_text()
LOGIN=read("HostApp/ScarletAppleIDLoginSheet.swift")
BRIDGE=read("HostApp/ScarletSideStoreAuthenticationBridge.swift")
XPC=read("HostApp/ScarletAuthXPCSupport.swift")
GUEST=read("integration/ScarletGuestSignInAgent.swift.txt")
PATCH=read("integration/wire_scarlet_auth.py")
HOST=read("HostApp/ScarletIntegratedHostView.swift")
INTEGRATOR=read("integration/apply_scarlet_host.py")
WORKFLOW=read("../.github/workflows/scarlet-paired-engines-build.yml")

class GuestSignInIntegration(unittest.TestCase):
    def test_placeholder_no_longer_owns_login_screen(self):
        self.assertIn("ScarletAppleIDLoginSheet(engine: ScarletConnectedSideSignEngine())",HOST)
        self.assertIn("func prepare() async throws",LOGIN)
        self.assertIn("transportReady",LOGIN)
        self.assertIn("try await engine.prepare()",LOGIN)
        self.assertIn('record("auth", "transport_ready"',LOGIN)
        self.assertNotIn("ScarletPendingSideStoreEngineBridge",HOST+LOGIN)
        self.assertNotIn("var isReady: Bool { false }",LOGIN)

    def test_real_auth_uses_side_sign_and_safe_2fa_callback(self):
        for marker in ("AnisetteProvider.fetch()", "AuthManager.shared.signIn(",
                       "verificationHandler:", "receiveUserCode(id)", ".verificationCode(code)",
                       "AuthManager.shared.xcodeToken", "AuthManager.shared.adsid",
                       "ScarletGuestAuthNeedsCode", "ScarletGuestAuthCompleted"):
            self.assertIn(marker,GUEST)
        for marker in ("scarletAuthReady", "scarletBeginAuth", "scarletProvideCode",
                       "scarletCancelAuth", "scarletAuthCompleted", "scarletEnsureAuthGuest"):
            self.assertIn(marker,XPC+PATCH)
        self.assertNotIn("UserDefaults.standard.set(password",GUEST)
        self.assertNotIn("print(password",GUEST)
        self.assertNotIn("NSLog(password",GUEST)
        self.assertNotIn("LCUtils.openSideStore(",HOST)

    def test_original_credentials_never_published_to_logs(self):
        self.assertIn('record("auth", "transport_preflight_failed"',LOGIN)
        self.assertIn('record("auth", "request_started"',LOGIN)
        self.assertIn('record("auth", "stored_session_verified"',LOGIN)
        self.assertIn('recordError("auth", "request_failed"',LOGIN)
        self.assertIn("remoteFailure(domain: String, code: Int)",XPC)
        self.assertIn("NotificationCenter.default.post",GUEST)
        self.assertNotIn("payload[\"password\"]",XPC)
        self.assertNotIn("fields: [\"password\"",LOGIN+XPC+HOST)

    def test_ipc_and_build_patches_are_pinned_and_fail_closed(self):
        self.assertIn('source.count("public final class AuthManager") == 1',PATCH)
        self.assertIn('assert "ScarletGuestSignInAgent" not in source',PATCH)
        self.assertIn('assert source.count("func signIn(appleID: String,") == 1',PATCH)
        self.assertIn("SideStoreSupport/XPCServer.h",PATCH)
        self.assertIn("SideStoreSupport/XPCClient.m",PATCH)
        self.assertIn("ScarletAuthXPCSupport.swift",PATCH)
        self.assertIn("ScarletSideStoreAuthenticationBridge.swift",INTEGRATOR)
        self.assertIn("--mode livecontainer",WORKFLOW)
        self.assertIn("--mode sidestore",WORKFLOW)
        self.assertIn("SCARLET_GUEST_IMPORT_PROGRESS_ONLY",INTEGRATOR)
        self.assertIn("FileManager.default.copyItem(at: source, to: temporary)",HOST)

    def test_login_state_changes_only_after_verified_guest_completion(self):
        self.assertIn("appleAuthenticated: appleAuthVerified",HOST)
        self.assertIn('Notification.Name("ScarletGuestAuthVerified")',HOST+LOGIN)
        self.assertIn('status: "success"',LOGIN)
        self.assertIn("private func finish(_ id: String, error: Error?)",XPC)
        self.assertIn("if let error { c.resume(throwing: error) } else { c.resume() }",XPC)
        self.assertIn("guard !cancelled else { throw CancellationError() }",GUEST)
        self.assertNotIn("pairingVerified: true",HOST)
        self.assertNotIn("signingVerified: true",HOST)

if __name__=="__main__":
    unittest.main()
