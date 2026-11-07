"""Regression tests for on-device November 7 guest launch/auth failures.

The synthetic upstream fixture exercises only the narrowly-scoped instrumentation.
A passed static test is not a verified signed-device run.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
BRIDGE = (ROOT/"HostApp/ScarletSideStoreAuthenticationBridge.swift").read_text()
GUEST_AGENT = (ROOT/"integration/ScarletGuestSignInAgent.swift.txt").read_text()
SHELL = (ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
PATCH = ROOT/"integration/apply_scarlet_host.py"


def integrator():
    spec = importlib.util.spec_from_file_location("scarlet_guest_diag", PATCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiveGuestAuthDiagnostics(unittest.TestCase):
    def test_duplicate_taps_are_deduplicated_before_original_runapp(self):
        self.assertIn("launchingGuestKeys.insert(key).inserted", HOST)
        self.assertIn("defer { launchingGuestKeys.remove(key) }", HOST)
        self.assertIn("try await app.runApp()", HOST)
        self.assertIn("launch_duplicate_ignored", HOST)

    def test_remote_error_reports_original_worker_domain_not_swift_enum_code_zero(self):
        self.assertIn("catch let error as ScarletNativeAuthError", BRIDGE)
        self.assertIn("case .remoteFailure(let domain, let code)", BRIDGE)
        self.assertIn('"auth", "remote_failure"', BRIDGE)
        self.assertIn('"domain": domain, "code": String(code)', BRIDGE)
        self.assertNotIn('"password": password', BRIDGE)
        self.assertNotIn('"appleID": appleID', BRIDGE)
        self.assertNotIn('"otp":', BRIDGE)

    def test_side_sign_swift_enum_index_three_is_not_apple_server_code(self):
        self.assertIn("catch let error as ServerError", GUEST_AGENT)
        self.assertIn("case .underlyingError(let appleCode, _)", GUEST_AGENT)
        self.assertIn('domain: "SideSign.ServerError.underlyingError"', GUEST_AGENT)
        self.assertIn("case .invalidAnisetteData:", GUEST_AGENT)
        self.assertIn("case .authenticationHandshakeFailed:", GUEST_AGENT)
        self.assertNotIn("jsonPayload)", GUEST_AGENT)
        self.assertNotIn('fields: ["password"', GUEST_AGENT)

    def test_guest_invalid_signature_has_non_destructive_recovery(self):
        self.assertIn("recordGuestCertificatePreflight()", HOST)
        self.assertIn("certificate_preflight", HOST)
        self.assertIn("team_match", HOST)
        self.assertIn("ScarletGuestCertificateInvalid", HOST)
        self.assertIn("ScarletOpenSigningSettings", HOST)
        self.assertIn("서명 설정에서 복구", HOST)
        self.assertIn("selected = .settings", SHELL)
        self.assertNotIn("SecItemDelete", HOST)
        self.assertNotIn("revokeCertificate", HOST)
        self.assertNotIn("LCUtils.appGroupUserDefault.set(nil", HOST)

    def test_signing_instrumentation_preserves_original_sign_calls_and_errors(self):
        source = '''import Foundation
class LCAppModel {
    func runApp() async throws {
        try await signApp(force: false)
    }
    func signApp(force: Bool = false) async throws {
        if let signError {
            if !signSuccess {
                throw signError.loc
            }
        }
    }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            engine = Path(tmp)
            file = engine/"LiveContainerSwiftUI/Models/LCAppModel.swift"
            file.parent.mkdir(parents=True)
            file.write_text(source)
            report = integrator().instrument_original_guest_signing(engine)
            result = file.read_text()
            self.assertTrue(report["originalLCSigningUnchanged"])
            self.assertTrue(report["originalLCLauncherUnchanged"])
            self.assertEqual(result.count("try await signApp(force: false)"), 1)
            self.assertEqual(result.count("throw signError.loc"), 1)
            for name in ("signing_started", "signing_completed", "signing_failed",
                         "signing_reason", "certificate_missing", "encrypted_binary"):
                self.assertIn(name, result)
            self.assertIn("ScarletGuestCertificateInvalid", result)
            self.assertNotIn("print(signError)", result)
            with self.assertRaises(AssertionError):
                integrator().instrument_original_guest_signing(engine)


if __name__ == "__main__":
    unittest.main()
