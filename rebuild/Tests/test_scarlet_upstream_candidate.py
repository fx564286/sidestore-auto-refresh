"""Upstream monitoring never silently updates the signing or host engine."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("candidate",ROOT/"scripts/scarlet_upstream_candidate.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
a,b,c,d,e="1"*40,"2"*40,"3"*40,"4"*40,"5"*40
pins={"LIVE_CONTAINER_REF":a,"EMBEDDED_SIDESTORE_REF":b,
      "MINIMUXER_REF":c,"SIDESIGN_REF":d}
old={"sideStoreAdvisory":{"head":a}}

class CandidateTests(unittest.TestCase):
    def test_no_change_does_not_create_candidate(self):
        result=mod.candidate(pins,old,pins,a)
        self.assertFalse(result["requiresIntegration"])
        self.assertFalse(result["autoRelease"])
        self.assertFalse(result["autoDeviceInstall"])

    def test_embedded_fork_changes_cascade_to_nested_gitlinks(self):
        next_pins={**pins,"EMBEDDED_SIDESTORE_REF":e,"SIDESIGN_REF":c}
        result=mod.candidate(pins,old,next_pins,a)
        self.assertTrue(result["requiresIntegration"])
        self.assertTrue(result["parentsChanged"])
        self.assertIn("SIDESIGN_REF",result["authoritativeChanges"])
        self.assertFalse(result["autoRelease"])

    def test_official_sidestore_is_advisory_not_embedded_replacement(self):
        result=mod.candidate(pins,old,pins,e)
        self.assertTrue(result["advisoryChanged"])
        self.assertFalse(result["parentsChanged"])
        self.assertEqual(result["updatedPins"],pins)
        self.assertFalse(result["sideStoreAdvisory"]["autoReplaceEmbeddedFork"])

    def test_incomplete_or_invalid_sha_rejected(self):
        with self.assertRaises(ValueError):
            mod.candidate({"LIVE_CONTAINER_REF":a},old,pins,a)
        with self.assertRaises(ValueError):
            mod.candidate(pins,old,{**pins,"SIDESIGN_REF":"bad"},a)
        with self.assertRaises(ValueError):
            mod.candidate(pins,old,pins,"bad")

    def test_original_glass_and_data_never_autoreleased(self):
        result=mod.candidate(pins,old,{**pins,"LIVE_CONTAINER_REF":e},e)
        self.assertTrue(result["originalGlassPreserved"])
        self.assertTrue(result["appIdentityPreserved"])
        self.assertTrue(result["reviewRequiredForUnknownAPIDiffs"])
        self.assertIn("test Apple login/2FA and installer in actual iPhone",result["prerequisites"])

if __name__=="__main__":
    unittest.main()
