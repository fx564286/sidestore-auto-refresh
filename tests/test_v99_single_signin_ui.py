"""V99 UI-only previous attempt diagnostic guard; auth engine stays unchanged."""
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEW = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text(encoding="utf-8")
POLICY = (ROOT / "scripts/templates/v3_behavioral_primitives.swift").read_text(encoding="utf-8")


class V99AuthSingleFlowTests(unittest.TestCase):
    def test_previous_failure_is_not_rendered_as_a_live_error(self):
        self.assertEqual(VIEW.count("SCARLET_V99_SINGLE_SIGNIN"), 1)
        start = VIEW.index("// SCARLET_V99_SINGLE_SIGNIN")
        end = VIEW.index("V3PromptSection(prompt:", start)
        guarded = VIEW[start:end]
        self.assertIn('DisclosureGroup("Previous sign-in attempt")', guarded)
        self.assertIn("V3AuthStore.failureMessage(from: previousFailure)", guarded)
        self.assertIn("V3AuthStore.failureDetails(from: previousFailure)", guarded)
        self.assertIn("Copy previous diagnostics", guarded)
        self.assertNotIn('Text(V3AuthStore.failureMessage(from: previousFailure))\n                                .font(.footnote)', guarded)

    def test_credential_prompt_state_is_not_an_error(self):
        self.assertEqual(VIEW.count("SCARLET_V99_PROMPT_STATUS"), 1)
        self.assertIn(' ? "Enter your Apple ID" : statusText)', VIEW)
        self.assertIn('V3PromptSection(prompt: prompt', VIEW)

    def test_previous_failure_retained_for_diagnostics(self):
        self.assertIn('(reply["previousFailure"] as? [String: Any]) ?? current', POLICY)
        self.assertIn('failure != nil && promptKind == "credentials"', POLICY)
        self.assertIn('promptKind == "credentials" ? nil : failure', POLICY)

    def test_only_one_live_credentials_flow_still_drives_side_store(self):
        view = VIEW[VIEW.index("struct V3SignInView: View"):VIEW.index("struct V3SignInView: View")+36000]
        self.assertIn("auth.answer(promptID:", view)
        self.assertIn("auth.begin()", view)
        self.assertNotIn("AuthManager.shared.signOut()", view)


if __name__ == "__main__":
    unittest.main()
