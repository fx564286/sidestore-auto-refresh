import importlib.util
import os
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
SIGNIN = (
    "NRG_GSA_RECOVERY_V1 V3_AUTH_FAILURE_PRESERVES_ACCOUNT_STATE_V1\n"
    + (v98.SIGN_ANCHOR + "\n                   " + v98.SIGN_OLD + " {\n"
       + "                    throw error\n                }\n") * 3
)

class V98AuthRegressionTests(unittest.TestCase):
    def test_auth_provenance_contains_phase_http_apple_code_and_families(self):
        result = v98.patch_auth(AUTH)
        self.assertEqual(result.count(v98.AUTH_MARKER), 1)
        for field in ("operation=", "http=", "apple_ec=", "anisette_family=", "sent_family="):
            self.assertIn(field, result)
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
            paths = (root / v98.AUTH_REL, root / v98.SIGN_REL)
            for path, data in zip(paths, (AUTH, SIGNIN)):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(data)
            with self.assertRaises(ValueError):
                v98.apply(root, check=True)
            v98.apply(root)
            before = [path.read_text() for path in paths]
            v98.apply(root)
            v98.apply(root, check=True)
            self.assertEqual(before, [path.read_text() for path in paths])

    def test_generated_integration_when_instructed(self):
        if os.environ.get("SCARLET_V98_PATCHED") == "1":
            root = Path(os.environ["SIDESTORE_TEST_SOURCE"])
            self.assertEqual(v98.patch_auth((root / v98.AUTH_REL).read_text()),
                             (root / v98.AUTH_REL).read_text())
            self.assertEqual(v98.patch_signin((root / v98.SIGN_REL).read_text()),
                             (root / v98.SIGN_REL).read_text())
        else:
            self.assertTrue(True)

if __name__ == "__main__":
    unittest.main()
