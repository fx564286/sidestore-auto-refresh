"""Contract tests for real post-signature entitlement audits."""
from pathlib import Path
import importlib.util
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"scripts/audit_signed_ipa_entitlements.py"
SPEC=importlib.util.spec_from_file_location("signed_ipa_entitlement_audit", FILE)
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class SignedIPAEntitlementAudit(unittest.TestCase):
    def test_signed_host_app_ids_are_both_observed_variants(self):
        self.assertEqual(len(MOD.EXPECTED_HOSTS),2)
        self.assertIn("com.kdt.livecontainer.P8EZT3U5N4.P8EZT3U5N4",
                      MOD.EXPECTED_HOSTS)

    def test_profile_must_authorize_exact_app_group(self):
        self.assertTrue(MOD.matches_profile(
            ["group.com.SideStore.SideStore.P8EZT3U5N4"],
            ["group.com.SideStore.SideStore.P8EZT3U5N4"]))
        self.assertFalse(MOD.matches_profile(
            ["group.com.SideStore.SideStore.P8EZT3U5N4"], []))
        self.assertFalse(MOD.matches_profile(True,False))
        self.assertFalse(MOD.matches_profile("wrong", "P8EZT3U5N4.*"))
        self.assertTrue(MOD.matches_profile(
            "P8EZT3U5N4.com.kdt.livecontainer.P8EZT3U5N4",
            "P8EZT3U5N4.*"))

    def test_unsigned_ipa_is_not_reported_as_authorized(self):
        # On macOS the checker must refuse an IPA with no codesign and
        # embedded Apple mobileprovision rather than fabricate a capability.
        src=FILE.read_text()
        self.assertIn('run("codesign", "--verify", "--strict"',src)
        self.assertIn('run("security", "cms", "-D", "-i"',src)
        self.assertIn("appGroupGrantedAndSigned",src)
        self.assertIn("verifiedDeviceInstallation\": False",src)
        self.assertIn("verifiedActualFeatureExecution\": False",src)

if __name__=="__main__":
    unittest.main()
