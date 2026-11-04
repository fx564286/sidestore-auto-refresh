"""V187: cancel RPC must never await an uncooperative Apple sign-in task.

Tests verify the exact source compiled from v3_headless_runtime.swift and
v3_sidestore_service.swift; no fake server completion and no UI/design changes.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/templates/v3_headless_runtime.swift"
SERVICE = ROOT / "scripts/templates/v3_sidestore_service.swift"
HOST = ROOT / "scripts/templates/v3_unified_shell.swift"


class V187AuthCancellationSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = RUNTIME.read_text()
        cls.service = SERVICE.read_text()

    def test_auth_cancel_never_waits_on_task_value(self):
        begin = self.runtime.index("    func requestCancellation(id: String) -> Bool {")
        end = self.runtime.index("    @discardableResult\n    private func finish(", begin)
        method = self.runtime[begin:end]
        self.assertIn("return cancel(id: id)", method)
        self.assertIn("return cancelBeforeBegin(id: id)", method)
        self.assertNotIn("await task.value", method)
        self.assertNotIn("task.value", method)
        self.assertNotIn("session.task?.value", method)
        self.assertNotIn("func cancelAndWait(id:", method)

    def test_service_uses_nonblocking_request_then_real_poll(self):
        start = self.service.index('        case "authCancel":')
        stop = self.service.index('        case "opRecoveryPrepare":', start)
        branch = self.service[start:stop]
        self.assertIn("auth.requestCancellation(id: target)", branch)
        self.assertIn("auth.poll(id: target)", branch)
        self.assertNotIn("await V3HeadlessRuntime.shared.auth", branch)
        self.assertNotIn('"state": "cancelled"', branch)
        self.assertNotIn('"stopConfirmed": true', branch)

    def test_pending_cancel_is_not_misreported_as_terminal(self):
        start = self.runtime.index("    func poll(id: String) -> [String: Any]? {")
        stop = self.runtime.index("    func respond(id:", start)
        poll = self.runtime[start:stop]
        self.assertIn('if let terminal = session.terminal.value', poll)
        self.assertIn('"cancellationRequested": session.cancellationRequested', poll)
        self.assertIn('"state": "working"', poll)
        self.assertNotIn('session.cancellationRequested ? "cancelled"', poll)

    def test_only_native_auth_run_produces_terminal(self):
        start = self.runtime.index("    func run(id: String) async {")
        end = self.runtime.index("    func poll(id:", start)
        run = self.runtime[start:end]
        self.assertIn("let result = try await operation.execute()", run)
        self.assertIn('finish(id: id, response: ["state": "cancelled"', run)
        self.assertIn("sessions[id]?.task = nil", run)

    def test_no_user_assets_or_signing_changed(self):
        self.assertNotIn("forceResign", self.runtime[self.runtime.index("func requestCancellation"):self.runtime.index("private func finish")])
        self.assertIn("SCARLET_V187_AUTH_CANCEL_NONBLOCKING", self.runtime)
        self.assertIn("V3SignInView", HOST.read_text())
        self.assertNotIn("ScarletV183HostLog.record(.authCancelTerminal)", self.service)


if __name__ == "__main__":
    unittest.main()
