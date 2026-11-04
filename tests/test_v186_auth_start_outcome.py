"""V186 regression: local Cancel must not become an Apple/backend failure."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name[:-3], ROOT / "scripts" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


v167 = load("patch_v167_restore_ondevice_pairing.py")
v182 = load("patch_v182_p00_auth_cancel_liveness.py")
v183 = load("patch_v183_host_diagnostic_logs.py")
v184 = load("patch_v184_auth_cancel_outcomes.py")
v185 = load("patch_v185_auth_owner_preflight.py")
v186 = load("patch_v186_auth_start_outcome.py")


class V186AuthBeginOutcomeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text()
        prepared = v182.patch(base)
        prepared += "\n// V167 pairing fixture.\n" + v167.METHOD
        cls.predecessor = v185.patch(v184.patch(v183.patch(prepared)))
        cls.patched = v186.patch(cls.predecessor)
        start = cls.patched.index("    private func run(sessionID requestedSession: String) async {")
        stop = cls.patched.index("    private func pollLoop(id:", start)
        cls.method = cls.patched[start:stop]

    def test_idempotent(self):
        self.assertEqual(v186.patch(self.patched), self.patched)
        self.assertEqual(self.patched.count(v186.MARK), 1)

    def test_distinguishes_cancel_from_transport_error(self):
        self.assertIn("if isCancelling || Task.isCancelled || error is CancellationError", self.method)
        self.assertIn("ScarletV183HostLog.record(.authBeginLocallyCancelled)", self.method)
        self.assertIn("ScarletV183HostLog.record(.authBeginRequestFailed)", self.method)
        self.assertEqual(self.method.count('requestDeadline: Date().addingTimeInterval(25)'), 1)

    def test_pending_marker_not_an_auth_result(self):
        self.assertIn("Task.sleep(nanoseconds: 10_000_000_000)", self.method)
        self.assertIn("self.authBeginPendingSessionID == requestedSession", self.method)
        self.assertIn("self.session == requestedSession, !self.isCancelling", self.method)
        self.assertIn("ScarletV183HostLog.record(.authBeginWaiting)", self.method)
        self.assertIn("authBeginPendingSessionID = nil", self.method)
        self.assertEqual(self.patched.count('"auth.begin_waiting"'), 1)
        self.assertEqual(self.patched.count('"auth.begin_locally_cancelled"'), 1)

    def test_provisioning_retry_and_ui_are_preserved(self):
        start = "    private func runProvisioningRetry(previouslyAvailable: Bool) async {"
        end = "    // V3_FINISH_LATER_PRESERVES_ACCOUNT_V1"
        self.assertEqual(
            self.predecessor[self.predecessor.index(start):self.predecessor.index(end)],
            self.patched[self.patched.index(start):self.patched.index(end)])
        start = "struct V3SignInLink: View {"
        end = "// SCARLET_V183_HOST_LOG_FALLBACK"
        self.assertEqual(
            self.predecessor[self.predecessor.index(start):self.predecessor.index(end)],
            self.patched[self.patched.index(start):self.patched.index(end)])

    def test_no_credentials_written_into_logs(self):
        for key in ("password", "appleID", "otp", "authorizationCode", "secret"):
            self.assertNotIn("ScarletV183HostLog.record(" + key, self.method)
        self.assertNotIn("ScarletV183HostLog.record(error", self.method)

    def test_fails_closed_without_v185(self):
        with self.assertRaisesRegex(ValueError, "requires V185"):
            v186.patch((ROOT / "scripts/templates/v3_unified_shell.swift").read_text())


if __name__ == "__main__":
    unittest.main()
