"""V93 regression: never treat arbitrary NSError code 3 as Apple portal failure."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('v93',ROOT/'scripts'/'patch_combined_service_startup.py')
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
class TypedProfileCauseTests(unittest.TestCase):
    def test_typed_auth_bound_failure_is_distinct_from_portal(self):
        s=v.SIGNING_CAUSE_HELPER
        self.assertIn('SCARLET_V93_PROFILE_TYPED_FAILURE',s)
        self.assertIn('failure == .notAuthenticated',s)
        self.assertIn('stage = "authentication"',s)
        self.assertIn('typedKind = "bound_auth_session_unavailable"',s)
        self.assertIn('typedKind = code == 8220 ? "portal_device_registration_8220" : "portal_server_reported"',s)
        self.assertIn('if error is CancellationError { throw error }',s)
        self.assertIn('NSLog("[SCARLET_V93_PROFILE_FAIL] role=%@ subtype=%@ typed=1"',s)
        self.assertNotIn('if errorCode == 3',s)
        self.assertNotIn('error as NSError).code == 3',s)
        self.assertIn('NSUnderlyingErrorKey: native',s)

    def test_untyped_provider_error_never_creates_recovery_guess(self):
        s=v.SIGNING_CAUSE_HELPER
        self.assertIn('typedKind = "other_non_cancellation"',s)
        self.assertIn('typedKind = "pipeline_operation_error"',s)
        self.assertIn('sourceStep = "provisioningProfileFetch"',s)
        self.assertIn('sourceStep = "provisioningProfileRetrieval"',s)

if __name__=="__main__":
    unittest.main()
