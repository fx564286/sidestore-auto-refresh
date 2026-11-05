#!/usr/bin/env python3
"""Contract test for V189 in-host auth transport boundary traces.

Unit test uses current pinned V3 SideStoreSupport bridge template; it does NOT
contact Apple or simulate successful authentication.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/patch_v189_auth_bridge_trace.py"
spec = importlib.util.spec_from_file_location("v189_bridge_trace", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def host_fixture():
    return '''
// SCARLET_V183_HOST_LOG_FALLBACK
enum ScarletV183Event: String {
    case authCancelRequested = "auth.cancel_requested"
    case authStarted = "auth.started"
}
enum ScarletV183HostLog {
    static func record(_ event: ScarletV183Event) {}
}
// SCARLET_V185_AUTH_HOST_OWNER_PREFLIGHT
final class V3AuthStore: ObservableObject {
    func begin() {
        guard canBegin else { return }
        ScarletV183HostLog.record(.authStarted)
        // Detect actual host shared-container access, never infer grants from an XML
        guard true else { return }
    }
}
'''


class TransportPhaseTests(unittest.TestCase):
    def test_instrument_real_pinned_service_bridge_source(self):
        path = ROOT / "scripts/templates/v3_service_bridge.swift"
        old = path.read_text(encoding="utf-8")
        new = mod.patch_bridge(old)
        self.assertEqual(mod.patch_bridge(new), new)
        for token in (
            'authPhaseObserver: ((String) -> Void)?',
            'traceAuthPhase(operation: operation, phase: "lease_waiting")',
            'traceAuthPhase(operation: operation, phase: "connect_started")',
            'traceAuthPhase(operation: operation, phase: "connect_ready")',
            'traceAuthPhase(operation: operation, phase: "connect_failed")',
            'traceAuthPhase(operation: operation, phase: "rpc_sent")',
            'traceAuthPhase(operation: operation, phase: "rpc_received")',
            'traceAuthPhase(operation: operation, phase: "rpc_timed_out")'
        ):
            self.assertIn(token, new)
        # Instrumentation must not duplicate remote Apple authentication.
        self.assertEqual(old.count('client.v3Execute(data)'), new.count('client.v3Execute(data)'))
        self.assertEqual(old.count('try await connect()'), new.count('try await connect()'))

    def test_exact_host_allowlist_no_secrets(self):
        new = mod.patch_host(host_fixture())
        self.assertEqual(mod.patch_host(new), new)
        self.assertEqual(new.count(mod.MARK), 1)
        self.assertEqual(new.count("ScarletV183HostLog.record(.authStarted)"), 1)
        self.assertEqual(new.count("authPhaseObserver = { phase in"), 1)
        for phase, raw in mod.PHASES:
            self.assertIn(f'"{phase}"', new)
            self.assertIn(f'"{raw}"', new)
        assert "password" not in new.lower()
        assert "token" not in new.lower()

    def test_reject_unreviewed_source_drift(self):
        old = (ROOT / "scripts/templates/v3_service_bridge.swift").read_text(encoding="utf-8")
        with self.assertRaises(ValueError):
            mod.patch_bridge(old.replace("public final class V3ServiceBridge", "class ChangedBridge"))
        with self.assertRaises(ValueError):
            mod.patch_host(host_fixture().replace('    case authCancelRequested = "auth.cancel_requested"\n', ''))


if __name__ == "__main__":
    unittest.main()
