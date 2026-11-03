"""P00 authentication-cancel liveness: source contract and idempotence tests.

The unit checks do not prove that Apple's login server or SideStore's XPC service
stopped. They ensure UI progress cannot rely on a cancelled Task.value and
that an unconfirmed backend outcome is retained as retryable/unknown.
"""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "p00_auth_cancel", ROOT / "scripts/patch_v182_p00_auth_cancel_liveness.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class P00AuthCancelLivenessTests(unittest.TestCase):
    def test_real_v3_cancel_patch(self):
        original = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text()
        updated = m.patch(original)
        self.assertEqual(m.patch(updated), updated)
        start = updated.index("    func cancel() {", updated.index("final class V3AuthStore"))
        end = updated.index("\nstruct V3SignInLink", start)
        cancel = updated[start:end]
        self.assertNotIn("await oldTask?.value", cancel)
        self.assertIn("requestDeadline: Date().addingTimeInterval(15)", cancel)
        self.assertIn("cancellationEpoch &+= 1", cancel)
        self.assertIn("isCancelling = false", cancel)
        self.assertIn('state = "resultUnknown"', cancel)
        self.assertIn("cancellationConfirmed = oldSession == nil || serverTerminal", cancel)
        self.assertIn("cancellationWasAttempted = !cancellationConfirmed", cancel)
        self.assertIn('operation: "authCancel"', cancel)

    def test_unrelated_ui_text_remains_unchanged(self):
        original = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text()
        updated = m.patch(original)
        self.assertEqual(original.count("struct V3PairingView: View"),
                         updated.count("struct V3PairingView: View"))
        self.assertEqual(original.count("struct V3PromptSection: View"),
                         updated.count("struct V3PromptSection: View"))
        before = original[original.index("struct V3PairingView: View"):]
        after = updated[updated.index("struct V3PairingView: View"):]
        self.assertEqual(before, after)

    def test_no_wrong_auth_store_is_patched(self):
        with self.assertRaises(ValueError):
            m.patch("final class V3AuthStore: ObservableObject {}\n")


if __name__ == "__main__":
    unittest.main()
