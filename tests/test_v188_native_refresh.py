"""V188 native refresh guard source tests, independent of device and Apple credentials."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/patch_v188_native_refresh.py"
spec = importlib.util.spec_from_file_location("v188", MODULE)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class NativeRefreshGuardTests(unittest.TestCase):
    def fake_upstream(self):
        return ("\nclass FetchProvisioningProfilesOperation: BasePipelineOperation {\n"
                + v.OLD_OVERRIDE
                + v.OLD_GROUP
                + v.OLD_RETURN
                + "\n}\nprivate extension FetchProvisioningProfilesOperation{\n"
                + "    func registerAppID() {}\n}\n")

    def test_patching_has_exact_group_and_all_four_bundle_ids(self):
        result = v.patch(self.fake_upstream())
        self.assertEqual(result.count(v.MARK), 1)
        self.assertIn(v.GROUP, result)
        for suffix in ("", ".LiveProcess", ".ShareExtension", ".LaunchAppExtension"):
            self.assertIn('"' + v.BASE + suffix + '"', result)
        self.assertEqual(v.patch(result), result)

    def test_invalid_custom_override_rejected(self):
        result = v.patch(self.fake_upstream())
        self.assertIn("cannot bypass Apple profile authorization", result)

    def test_apple_grants_and_certificate_checked(self):
        result = v.patch(self.fake_upstream())
        for key in ("com.apple.security.application-groups", "keychain-access-groups",
                    "com.apple.developer.kernel.increased-memory-limit",
                    "profile.certificates", "targetSigningCertificate",
                    "profile.expirationDate > Date()"):
            self.assertIn(key, result)

    def test_no_new_ids_or_revoke_operations_in_protected_path(self):
        result = v.patch(self.fake_upstream())
        self.assertIn("fetchAppGroups(for: team)", result)
        self.assertIn("assignAppID(", result)
        self.assertNotIn("DeveloperPortalProxy.shared.addAppGroup(", result)
        self.assertNotIn("DeveloperPortalProxy.shared.addAppID(", result)
        self.assertNotIn("DeveloperPortalProxy.shared.revoke", result)

    def test_missing_upstream_anchor_stops(self):
        with self.assertRaises(ValueError):
            v.patch(self.fake_upstream().replace(v.OLD_GROUP, ""))

if __name__ == "__main__":
    unittest.main()
