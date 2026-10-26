"""V123: check expired provisioning session recovery UI without secrets."""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"scripts/templates/v3_unified_shell.swift"

class V123ReauthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        full=SOURCE.read_text(encoding="utf-8")
        cls.view=full.split("struct V3SignInView: View {",1)[1].split("// V3_CERTIFICATE_CREATE_PRESENTATION_V1",1)[0]

    def test_expired_session_offers_new_interactive_sign_in(self):
        v=self.view
        self.assertIn("SCARLET_V123_REAUTH_RECOVERY",v)
        self.assertIn("if auth.provisioningSessionUnavailable {\n                        if auth.canBegin {",v)
        self.assertIn('Label("Sign In Again to Complete Setup"',v)
        self.assertIn("auth.begin()",v)
        self.assertIn("!auth.provisioningSessionUnavailable &&",v)

    def test_finish_later_closes_without_deleting_account(self):
        self.assertIn("@Environment(\\.dismiss) private var dismiss",self.view)
        action=self.view.split("private func finishProvisioningLater() {",1)[1].split("}",1)[0]
        for key in ("auth.finishProvisioningLater()","status.reload()","dismiss()"):
            self.assertIn(key,action)
        for forbidden in ("signOut","remove","clearAll","reset"):
            self.assertNotIn(forbidden,action)

    def test_only_existing_auth_admission_is_invoked(self):
        block=self.view.split("// SCARLET_V123_REAUTH_RECOVERY",1)[1].split("if recovery.blockedByActiveSession",1)[0]
        self.assertIn("auth.canBegin",block)
        self.assertIn("auth.begin()",block)
        for forbidden in ("AuthManager.shared","Keychain","adiPb","deleteAppID"):
            self.assertNotIn(forbidden,block)

if __name__=="__main__":
    unittest.main()
