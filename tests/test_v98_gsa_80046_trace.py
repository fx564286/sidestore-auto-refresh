import importlib.util
import os
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("scarlet_v98", ROOT / "scripts/patch_v98_gsa_80046_trace.py")
v98 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v98)

AUTH = (
    "NRG_GSA_RECOVERY_V1 NRG_GSA_HTTP_STATUS_V2 NRG_GSA_CLIENT_IDENTITY_V3\n"
    + v98.AUTH_OLD + '            throw ServerError.underlyingError(code: errorCode, message: errorDesc ?? "Authentication failed")\n'
)
LOG = (
    "import Foundation\n// SIDESIGN_USER_LOG_PRIVACY_V1\n"
    + v98.LOG_BASE + "\n\n" + v98.LOG_ANCHOR + "\n    _ = text\n}\n"
)
SIGNIN = (
    "NRG_GSA_RECOVERY_V1 V3_AUTH_FAILURE_PRESERVES_ACCOUNT_STATE_V1\n"
    + (v98.SIGN_ANCHOR + "\n                   " + v98.SIGN_OLD + " {\n"
       + "                    throw error\n                }\n") * 3
)

class V98AuthRegressionTests(unittest.TestCase):
    def test_auth_provenance_contains_phase_http_apple_code_and_families(self):
        result = v98.patch_auth(AUTH)
        self.assertEqual(result.count(v98.AUTH_MARKER), 1)
        self.assertIn('nrgLogSafeAuthPhase(operation: safeOperation', result)
        self.assertNotIn('debugLog("[SCARLET_V98_GSA]', result)
        safe_sink = v98.patch_log(LOG)
        for field in ("[SCARLET_V98_GSA] operation=", "http=", "apple_ec=",
                      "anisette_family=", "sent_family="):
            self.assertIn(field, safe_sink)
        self.assertIn(v98.LOG_MARKER, safe_sink)
        self.assertEqual(v98.patch_auth(result), result)

    def test_auth_does_not_log_raw_apple_response_or_identity(self):
        result = v98.patch_auth(AUTH)
        self.assertNotIn('error code \\(errorCode): \\(errorDesc', result)
        self.assertNotIn('debugLog("\\(errorDesc)', result)
        self.assertIn('throw ServerError.underlyingError(code: errorCode, message: errorDesc', result)
        self.assertIn('"init", "complete", "apptokens"', result)

    def test_auth_rejects_missing_prior_gsa_patches(self):
        with self.assertRaises(ValueError):
            v98.patch_auth(v98.AUTH_OLD)

    def test_auth_rejects_reordered_or_duplicate_anchor(self):
        with self.assertRaises(ValueError):
            v98.patch_auth(AUTH + v98.AUTH_OLD)
        with self.assertRaises(ValueError):
            v98.patch_auth(AUTH.replace(v98.AUTH_OLD, "invalid"))

    def test_signin_all_three_terminal_paths_include_80046(self):
        result = v98.patch_signin(SIGNIN)
        self.assertEqual(result.count(v98.SIGN_NEW), 3)
        self.assertEqual(result.count(v98.SIGN_MARKER), 1)
        self.assertNotIn(v98.SIGN_OLD, result)
        self.assertEqual(v98.patch_signin(result), result)

    def test_signin_rejects_partial_or_destructive_state(self):
        with self.assertRaises(ValueError):
            v98.patch_signin(SIGNIN.replace(v98.SIGN_OLD, "-80046", 1))
        with self.assertRaises(ValueError):
            v98.patch_signin(SIGNIN + "AuthManager.shared.signOut()")

    def test_apply_is_idempotent_and_check_requires_complete_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = (root / v98.AUTH_REL, root / v98.SIGN_REL, root / v98.LOG_REL)
            for path, data in zip(paths, (AUTH, SIGNIN, LOG)):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data)
            with self.assertRaises(ValueError):
                v98.apply(root, check=True)
            v98.apply(root)
            before = [path.read_text() for path in paths]
            v98.apply(root)
            v98.apply(root, check=True)
            self.assertEqual(before, [path.read_text() for path in paths])

    def test_safe_sink_only_accepts_bounded_public_diagnostic_fields(self):
        patched = v98.patch_log(LOG)
        self.assertEqual(v98.patch_log(patched), patched)
        self.assertIn(v98.LOG_BASE, patched)
        self.assertIn('["init", "complete", "apptokens"]', patched)
        self.assertIn('["windows", "mac", "android"]', patched)
        self.assertIn('(0...599).contains(httpStatus)', patched)
        self.assertIn('(-1000000...1000000).contains(appleCode)', patched)
        self.assertNotIn('debugLog("[SCARLET_V98_GSA]', patched)
        for forbidden in ('unsanitizedAppleID', 'verificationHandler',
                          'passwordData', 'oneTimePassword', 'rawResponse',
                          'sessionToken', 'Authorization:'):
            self.assertNotIn(forbidden, v98.LOG_INSERT)

    def test_unpatched_general_logging_is_never_accepted(self):
        with self.assertRaisesRegex(ValueError, 'privacy-disabled'):
            v98.patch_log(LOG.replace('    _ = text', '    print(text())'))
        with self.assertRaisesRegex(ValueError, 'privacy-disabled'):
            v98.patch_log(LOG.replace('SIDESIGN_USER_LOG_PRIVACY_V1', 'NO_PRIVACY'))
        with self.assertRaisesRegex(ValueError, 'logging anchor'):
            v98.patch_log(LOG.replace(v98.LOG_ANCHOR, 'func verboseUnknown() {'))
        with self.assertRaisesRegex(ValueError, 'drifted'):
            v98.patch_log(v98.patch_log(LOG).replace('apple_ec=', 'secret='))

    def test_safe_sink_release_swift_execution(self):
        # macOS CI must execute this real Swift harness. This test does not
        # require credentials, an Apple ID, or external network requests.
        compiler = shutil.which('swiftc')
        if not compiler:
            return
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'Harness.swift'
            exe = Path(tmp) / 'Harness'
            source.write_text("""import Foundation
func getTag(level: String) -> String { return level + " " }
""" + v98.LOG_INSERT + r'''@main struct TestSafeSink {
    static func main() {
        nrgLogSafeAuthPhase(operation: "PRIVATE_EMAIL_SECRET", httpStatus: 200,
                            appleCode: -80046, anisetteFamily: "PRIVATE_TOKEN_SECRET",
                            sentFamily: "mac")
        nrgLogSafeAuthPhase(operation: "init", httpStatus: 9000,
                            appleCode: 999999999, anisetteFamily: "windows",
                            sentFamily: "PRIVATE_ID_SECRET")
    }
}
''')
            subprocess.run([compiler, '-O', '-parse-as-library', str(source),
                            '-o', str(exe)], capture_output=True, text=True,
                           check=True, timeout=60)
            # Same RELEASE-mode raw marker gate as verify_candidate_ipa:
            # never claim the diagnostic exists merely because source mentions it.
            self.assertIn(b'[SCARLET_V98_GSA] operation=', exe.read_bytes(),
                          'Swift Release optimization eliminated the GSA diagnostic marker')
            output = subprocess.run([str(exe)], capture_output=True, text=True,
                                    check=True, timeout=20).stdout
            self.assertIn('[SCARLET_V98_GSA] operation=other http=200 apple_ec=-80046 anisette_family=other sent_family=mac', output)
            self.assertIn('[SCARLET_V98_GSA] operation=init http=0 apple_ec=0 anisette_family=windows sent_family=other', output)
            self.assertNotIn('PRIVATE_', output)

    def test_generated_integration_when_instructed(self):
        if os.environ.get("SCARLET_V98_PATCHED") == "1":
            root = Path(os.environ["SIDESTORE_TEST_SOURCE"])
            self.assertEqual(v98.patch_auth((root / v98.AUTH_REL).read_text()),
                             (root / v98.AUTH_REL).read_text())
            self.assertEqual(v98.patch_signin((root / v98.SIGN_REL).read_text()),
                             (root / v98.SIGN_REL).read_text())
            self.assertEqual(v98.patch_log((root / v98.LOG_REL).read_text()),
                             (root / v98.LOG_REL).read_text())
        else:
            self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
