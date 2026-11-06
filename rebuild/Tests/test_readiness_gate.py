"""Fail-closed evidence semantics for source-vs-runtime Scarlet validation."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
path=ROOT/"rebuild/scripts/audit_readiness.py"
spec=importlib.util.spec_from_file_location("scarlet_readiness",path)
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class ReleaseReadinessTests(unittest.TestCase):
    def test_all_requirements_have_explicit_status(self):
        r=audit.assess(ROOT)
        self.assertEqual(r["visualScreenCount"],6)
        self.assertEqual(len(r["checks"]),11)
        ids=[x["id"] for x in r["checks"]]
        self.assertEqual(len(set(ids)),len(ids))
        for key in ["original_native_liquid_glass","window_manager_gestures",
                    "real_device_visual_regression","apple_login_pairing_2fa",
                    "signed_ipa_and_user_data"]:
            self.assertIn(key,ids)

    def test_source_typecheck_does_not_claim_real_glass(self):
        r=audit.assess(ROOT)
        self.assertTrue(r["simulatorEvidenceIsNotNativeGlass"])
        release_blockers=[x["id"] for x in r["checks"]
                          if x["releaseRequired"] and x["status"]!="passed"]
        self.assertEqual(r["blockingChecks"],release_blockers)
        self.assertEqual(r["releaseReady"],not bool(release_blockers))
        # For the current new-source-only branch, native renderer absent:
        host=ROOT/"rebuild/HostApp"
        if not host.exists():
            self.assertIn("original_native_liquid_glass",release_blockers)
            self.assertIn("livecontainer_host_integration",release_blockers)

if __name__=="__main__":
    unittest.main()
