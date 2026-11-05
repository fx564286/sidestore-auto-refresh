#!/usr/bin/env python3
"""V191 contract: authBegin's deadline must bound status-lease waiting.

Tests operate on pinned V3 bridge and V189 tracer source. No Apple calls.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


def load(path, name):
    spec=importlib.util.spec_from_file_location(name, ROOT/path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


trace=load("scripts/patch_v189_auth_bridge_trace.py","scarlet_trace189")
lease=load("scripts/patch_v191_auth_lease_deadline.py","scarlet_lease191")


def fixture():
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


class AuthLeaseDeadlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline=(ROOT/"scripts/templates/v3_service_bridge.swift").read_text()
        cls.traced=trace.patch_bridge(cls.baseline)
        cls.patched=lease.patch_bridge(cls.traced)

    def test_deadline_before_connect_and_before_xpc(self):
        text=self.patched
        self.assertEqual(lease.patch_bridge(text),text)
        self.assertIn("deadline: Date? = nil",text)
        self.assertIn("deadline: requestDeadline",text)
        self.assertIn('traceAuthPhase(operation: operation, phase: "lease_unavailable")',text)
        req=text.index("public func request(operation: String")
        acquire=text.index("statusLeaseTicket = try await acquireStatusLease(",req)
        connect=text.index("try await connect()",req)
        dispatch=text.index("client.v3Execute(data)",req)
        self.assertLess(acquire,connect)
        self.assertLess(connect,dispatch)
        self.assertEqual(self.traced.count("client.v3Execute(data)"),text.count("client.v3Execute(data)"))
        self.assertEqual(self.traced.count("try await connect()"),text.count("try await connect()"))

    def test_timeout_removes_only_queued_waiter(self):
        fragment=self.patched.split("private func timeoutStatusLeaseWaiter(",1)[1].split(
            "private func drainStatusLeaseWaiters()",1)[0]
        self.assertIn("statusLeaseWaiterOrder.remove(waiterID)",fragment)
        self.assertIn("statusLeaseWaiters.remove(at: index)",fragment)
        self.assertIn("waiter.continuation.resume(throwing:",fragment)
        self.assertNotIn("statusWriteAuthority.complete(",fragment)
        self.assertNotIn("statusWriteAuthority.retireService(",fragment)
        self.assertNotIn("v3_stopService(",fragment)
        self.assertNotIn("statusWriteAuthority.activeLease =",fragment)

    def test_deadline_task_cancelled_on_return_and_no_double_completion(self):
        fragment=self.patched.split("private func acquireStatusLease(",1)[1].split(
            "private func cancelStatusLeaseWaiter(",1)[0]
        self.assertIn("defer { leaseDeadlineTask?.cancel() }",fragment)
        self.assertIn("self?.timeoutStatusLeaseWaiter(waiterID)",fragment)
        self.assertIn("catch { return }",fragment)
        self.assertIn("statusLeaseWaiters.append(StatusLeaseWaiter(",fragment)
        self.assertIn("withCheckedThrowingContinuation",fragment)

    def test_lease_outcome_is_not_claimed_apple_failure(self):
        text=self.patched
        self.assertIn("V3AuthAttemptStartFailurePolicy.confirmedNotDispatched(",text)
        self.assertIn('traceAuthPhase(operation: operation, phase: "lease_cancelled")',text)
        self.assertIn('traceAuthPhase(operation: operation, phase: "lease_blocked_snapshot")',text)
        self.assertIn('traceAuthPhase(operation: operation, phase: "lease_blocked_mutation")',text)
        self.assertIn('traceAuthPhase(operation: operation, phase: "lease_blocked_unresolved")',text)
        self.assertIn('traceAuthPhase(operation: operation, phase: "lease_blocked_queue")',text)

    def test_host_logger_exact_allowlist_without_credentials(self):
        host=trace.patch_host(fixture())
        patched=lease.patch_host(host)
        self.assertEqual(lease.patch_host(patched),patched)
        self.assertEqual(patched.count(lease.MARK),1)
        self.assertEqual(len(lease.PHASES),6)
        for offset,(phase,event) in enumerate(lease.PHASES,start=15):
            self.assertIn(f'case trace{offset} = "{event}"',patched)
            self.assertIn(f'case "{phase}": ScarletV183HostLog.record(.trace{offset})',patched)
        self.assertNotIn("Apple ID",patched)
        self.assertNotIn("password",patched.lower())
        self.assertNotIn("github_pat_",patched)

    def test_reject_source_drift_and_missing_v189(self):
        with self.assertRaises(ValueError):
            lease.patch_bridge(self.baseline)
        with self.assertRaises(ValueError):
            lease.patch_bridge(self.traced.replace("private func drainStatusLeaseWaiters()", "private func drainWaiters()"))
        with self.assertRaises(ValueError):
            lease.patch_host(fixture())


if __name__=="__main__":
    unittest.main()
