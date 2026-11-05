#!/usr/bin/env python3
"""Regression tests for V189 visible login; no Apple ID, key or live service used."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).parents[1] / "scripts" / "patch_v189_login_entry.py"
spec = importlib.util.spec_from_file_location("v189_visible_login", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fixture():
    return '''
// SCARLET_V189_CANCEL_INTENT_PER_SESSION
final class V3AuthStore: ObservableObject {
    private var promptResponseGeneration: UInt64 = 0
    func begin() {}
    var canBegin: Bool {
        true
    }
    private func run(sessionID requestedSession: String) async {
        let sessionDeadline = Date()
    }
    private func apply(_ reply: [String: Any]) {
        let oldPromptID = prompt?["id"] as? String
        let replyState = reply["state"] as? String ?? state
        let isTerminal = false
        state = replyState
        prompt = reply["prompt"] as? [String: Any]
        if oldPromptID != (prompt?["id"] as? String) {
            promptSubmitting = false
        }
        if state == "completed" {
            message = ""
        }
    }
    func answer(promptID: String, answer: [String: String]) {}
    func cancel() {
        guard !(state == "resultUnknown" && session == nil) else {
            return
        }
    }
}
struct V3SignInView: View {
    @ObservedObject private var auth = V3AuthStore.shared
    var body: some View {
        List {
            Section("Apple ID") {
                HStack {
                    Text("Status")
                }
                if auth.isSignedIn {
                    Text("Signed in")
                }
                if auth.state == "idle" {
                    Button { auth.begin() } label: { Text("Begin Sign In") }
                } else {
                    Button { auth.begin() } label: { Text("Retry") }
                    Button("Begin Sign-In After Repair") { auth.begin() }
                    Button("Use App-Specific Password") { auth.begin() }
                }
                Button("Sign In Again") { auth.begin() }
            }
        }
        .onDisappear {
            auth.cancel()
            auth.clearPreviousFailure()
            // The root auth-event observer owns certificate-readiness
            status.reload()
        }
    }
}
struct NextView: View {}
'''


class VisibleLoginTests(unittest.TestCase):
    def test_immediate_credential_fields_and_exact_prompt_handshake(self):
        modified = module.patch(fixture())
        self.assertIn("TextField(\"Apple ID\", text: $preparedAppleID)", modified)
        self.assertIn("SecureField(\"Password\", text: $preparedPassword)", modified)
        self.assertIn("beginWithCredentials(appleID: appleID, password: password)", modified)
        self.assertIn("queued.sessionID == session", modified)
        self.assertIn('currentPrompt["kind"] as? String == "credentials"', modified)
        self.assertIn('"appleID": queued.appleID, "password": queued.password', modified)
        self.assertIn('if isTerminal { queuedLogin = nil }', modified)
        self.assertIn("queuedLogin?.sessionID == requestedSession", modified)
        self.assertIn("if patch(src) != src:", SCRIPT.read_text())
        self.assertEqual(module.patch(modified), modified)

    def test_navigation_does_not_implicitly_cancel_auth(self):
        modified = module.patch(fixture())
        view = modified.split("struct V3SignInView: View {", 1)[1].split("struct NextView:", 1)[0]
        self.assertNotIn("auth.begin()", view)
        self.assertNotIn("auth.cancel()", view)
        self.assertIn("showCredentialEntry = true", view)
        self.assertIn("preparedPassword = \"\"", view)
        self.assertIn("textContentType(.oneTimeCode)", (Path(__file__).parents[1] /
            "scripts/templates/v3_unified_shell.swift").read_text())

    def test_drift_fail_closed(self):
        self.assertRaises(ValueError, module.patch, fixture().replace(
            "    private var promptResponseGeneration: UInt64 = 0", "    let other = true"))
        self.assertRaises(ValueError, module.patch, fixture().replace(
            "// SCARLET_V189_CANCEL_INTENT_PER_SESSION", "// missing predecessor"))


if __name__ == "__main__":
    unittest.main()
