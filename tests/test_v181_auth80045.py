"""V181 Android/Windows Anisette client identity compatibility and recovery."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("v181", ROOT / "scripts/patch_v181_auth80045.py")
v181 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v181)
RAW_AUTH = """import Foundation
import GSACryptoKit

let first = [
            "User-Agent": h.grandSlam.userAgent,
]
let two = [
            "User-Agent": h.developerServices.userAgent,
]
"""
RAW_HANDLER = """import UIKit
import SideSign
func signInHandler() {
            case .failure(let error):
                completionHandler(.failure(error))
}
"""

class Auth80045Tests(unittest.TestCase):
    def test_gsa_two_factor_consistent_with_explicit_compatibility_profile(self):
        out = v181.patch_sidesign(RAW_AUTH)
        self.assertEqual(out, v181.patch_sidesign(out))
        self.assertEqual(out.count("scarletV181CompatibleUserAgent("), 3)
        self.assertIn("clientInfo: anisetteData.clientInfo", out)
        self.assertIn("clientInfo: a.clientInfo", out)
        self.assertIn("fallback == defaultAgent", out)
        self.assertIn("compatibleProfile && fallback == defaultAgent", out)
        self.assertIn('return "akd/1.0 CFNetwork/808.1.4"', out)
        self.assertNotIn("adiPb =", out)
        self.assertNotIn("SecItemDelete(", out)
        self.assertNotIn("resetAnisette", out)

    def test_user_overrides_and_no_unilateral_profile_switch(self):
        out = v181.patch_sidesign(RAW_AUTH)
        self.assertIn("return fallback", out)
        self.assertIn("clientInfo.contains(\"<Windows;\")", out)
        self.assertIn("clientInfo.contains(\"<Android;\")", out)
        self.assertNotIn("<Pixel 7>", out)
        self.assertNotIn("retries", out.lower())

    def test_bad_upstream_anchor_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "expected one exact upstream"):
            v181.patch_sidesign(RAW_AUTH.replace("h.grandSlam.userAgent", "otherAgent"))
        with self.assertRaisesRegex(ValueError, "expected one exact upstream"):
            v181.patch_handler("import SideSign\n")

    def test_actionable_error_mapping_preserves_signin_control(self):
        out = v181.patch_handler(RAW_HANDLER)
        self.assertEqual(v181.patch_handler(out), out)
        self.assertIn("code == -80045", out)
        self.assertIn("Anisette Client Configuration", out)
        self.assertIn("completionHandler(.failure(error))", out)
        self.assertNotIn("signOut()", out)
        self.assertNotIn("SecItemDelete", out)
        self.assertNotIn("resetAnisette", out)

if __name__ == "__main__":
    unittest.main()
