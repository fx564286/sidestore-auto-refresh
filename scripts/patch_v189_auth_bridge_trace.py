#!/usr/bin/env python3
"""V189 service-boundary instrumentation for otherwise invisible authBegin stalls.

The existing auth.begin_dispatched event is emitted BEFORE SideStore XPC
connect/admission. Distinguish admission, status lease, extension readiness,
actual v3Execute send, reply and cancellation. Log fixed event names ONLY.
This preserves the authentication protocol, signing material, account data,
Liquid Glass UI, and SideStore service state.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V189_AUTH_TRANSPORT_PHASE_TRACE"
BRIDGE = Path("SideStoreSupport/SideStore.swift")
HOST = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")

PHASES = (
    ("begin.admission_passed", "auth.rpc.admitted"),
    ("begin.lease_waiting", "auth.rpc.lease_waiting"),
    ("begin.lease_acquired", "auth.rpc.lease_acquired"),
    ("begin.connect_started", "auth.rpc.connect_started"),
    ("begin.connect_ready", "auth.rpc.connect_ready"),
    ("begin.connect_failed", "auth.rpc.connect_failed"),
    ("begin.rpc_sent", "auth.rpc.sent"),
    ("begin.rpc_received", "auth.rpc.received"),
    ("begin.rpc_timed_out", "auth.rpc.timed_out"),
    ("cancel.admission_passed", "auth.cancel_rpc.admitted"),
    ("cancel.connect_started", "auth.cancel_rpc.connect_started"),
    ("cancel.connect_ready", "auth.cancel_rpc.connect_ready"),
    ("cancel.connect_failed", "auth.cancel_rpc.connect_failed"),
    ("cancel.rpc_sent", "auth.cancel_rpc.sent"),
    ("cancel.rpc_received", "auth.cancel_rpc.received"),
    ("cancel.rpc_timed_out", "auth.cancel_rpc.timed_out"),
)

def once(s: str, old: str, new: str, label: str) -> str:
    n = s.count(old)
    if n != 1:
        raise ValueError(f"V189 auth transport {label}: source anchor count={n}, expected 1")
    return s.replace(old, new, 1)

def patch_bridge(s: str) -> str:
    if MARK in s:
        if s.count(MARK) != 1 or 'traceAuthPhase(operation: operation, phase: "rpc_sent")' not in s:
            raise ValueError("incomplete installed bridge phase trace")
        return s
    if "public final class V3ServiceBridge {" not in s:
        raise ValueError("SideStore host service bridge missing")
    s = once(s,
        "    public static let shared = V3ServiceBridge()\n",
        """    public static let shared = V3ServiceBridge()
    // SCARLET_V189_AUTH_TRANSPORT_PHASE_TRACE:
    // Fixed phase labels only. Never pass identifiers, passwords or request data.
    public var authPhaseObserver: ((String) -> Void)?
    private func traceAuthPhase(operation: String, phase: String) {
        switch operation {
        case "authBegin": authPhaseObserver?("begin." + phase)
        case "authCancel": authPhaseObserver?("cancel." + phase)
        default: break
        }
    }
""",
        "tracer contract")
    s = once(s,
        "        defer { if activeMutation == id { activeMutation = nil } }\n",
        """        defer { if activeMutation == id { activeMutation = nil } }
        traceAuthPhase(operation: operation, phase: "admission_passed")
""",
        "admission")
    s = once(s,
        "        if let statusOwnerID, let statusLeaseKind {\n"
        "            statusLeaseTicket = try await acquireStatusLease(ownerID: statusOwnerID, kind: statusLeaseKind,\n"
        "                allowUnresolvedMutation: explicitDirectRecoveryControl)\n",
        """        if let statusOwnerID, let statusLeaseKind {
            traceAuthPhase(operation: operation, phase: "lease_waiting")
            statusLeaseTicket = try await acquireStatusLease(ownerID: statusOwnerID, kind: statusLeaseKind,
                allowUnresolvedMutation: explicitDirectRecoveryControl)
            traceAuthPhase(operation: operation, phase: "lease_acquired")
""",
        "bounded status lease observability")
    s = once(s,
        """            do {
                try await connect()
            } catch {
                // The first connect() has failed BEFORE pending[id] and XPC
""",
        """            do {
                traceAuthPhase(operation: operation, phase: "connect_started")
                try await connect()
                traceAuthPhase(operation: operation, phase: "connect_ready")
            } catch {
                // The first connect() has failed BEFORE pending[id] and XPC
""",
        "extension connection")
    s = once(s,
        "                try await connect()\n"
        "            }\n"
        "            if let connectedTicket = observeConnectedStatusService(ownerID: statusOwnerID ??\n",
        "                traceAuthPhase(operation: operation, phase: \"connect_started\")\n"
        "                try await connect()\n"
        "                traceAuthPhase(operation: operation, phase: \"connect_ready\")\n"
        "            }\n"
        "            if let connectedTicket = observeConnectedStatusService(ownerID: statusOwnerID ??\n",
        "safe pre-dispatch reconnect")
    s = once(s,
        """        } catch {
            if ["authBegin", "authRetryProvisioning"].contains(operation) {
                NotificationCenter.default.post(name: Notification.Name("V3AuthIdentityTransitionFinished"), object: nil)
            }
            if error is CancellationError { throw CancellationError() }
""",
        """        } catch {
            traceAuthPhase(operation: operation, phase: "connect_failed")
            if ["authBegin", "authRetryProvisioning"].contains(operation) {
                NotificationCenter.default.post(name: Notification.Name("V3AuthIdentityTransitionFinished"), object: nil)
            }
            if error is CancellationError { throw CancellationError() }
""",
        "connection failure")
    s = once(s,
        """                statusDispatchedRequestIDs.insert(id)
                client.v3Execute(data) { response in
                    Task { @MainActor in
                        self.observeStatusLeaseResponse(requestID: id, operation: operation,
""",
        """                statusDispatchedRequestIDs.insert(id)
                traceAuthPhase(operation: operation, phase: "rpc_sent")
                client.v3Execute(data) { response in
                    Task { @MainActor in
                        self.traceAuthPhase(operation: operation, phase: "rpc_received")
                        self.observeStatusLeaseResponse(requestID: id, operation: operation,
""",
        "actual XPC command and callback")
    s = once(s,
        """                    if self.pending[id] != nil {
                        let retireIfStuck = V3RequestRetirementPolicy
""",
        """                    if self.pending[id] != nil {
                        self.traceAuthPhase(operation: operation, phase: "rpc_timed_out")
                        let retireIfStuck = V3RequestRetirementPolicy
""",
        "actual request timeout")
    if patch_bridge(s) != s:
        raise ValueError("bridge patch not idempotent")
    return s


def patch_host(s: str) -> str:
    if MARK in s:
        if s.count(MARK) != 1 or 'V3ServiceBridge.shared.authPhaseObserver = { phase in' not in s:
            raise ValueError("incomplete installed host phase trace")
        return s
    if "SCARLET_V185_AUTH_HOST_OWNER_PREFLIGHT" not in s or "SCARLET_V183_HOST_LOG_FALLBACK" not in s:
        raise ValueError("V185 host-owned auth and V183 persistent logs required")
    events = "".join(
        f'    case trace{idx} = "{raw}"\n' for idx, (_, raw) in enumerate(PHASES)
    )
    s = once(s,
        '    case authCancelRequested = "auth.cancel_requested"\n',
        '    case authCancelRequested = "auth.cancel_requested"\n'
        f'    // {MARK}: exact transport boundary, no request payload.\n' + events,
        "host allowlisted event names")
    cases = "\n".join(
        f'            case "{phase}": ScarletV183HostLog.record(.trace{idx})'
        for idx, (phase, _) in enumerate(PHASES)
    )
    s = once(s,
        '        ScarletV183HostLog.record(.authStarted)\n'
        '        // Detect actual host shared-container access',
        '        ScarletV183HostLog.record(.authStarted)\n'
        '        V3ServiceBridge.shared.authPhaseObserver = { phase in\n'
        '            switch phase {\n' + cases + '\n'
        '            default: break\n'
        '            }\n'
        '        }\n'
        '        // Detect actual host shared-container access',
        "register transport events at user login start")
    if patch_host(s) != s:
        raise ValueError("host patch not idempotent")
    return s


def apply(root: Path) -> None:
    paths = (root / BRIDGE, root / HOST)
    if any(not p.is_file() or p.is_symlink() for p in paths):
        raise ValueError("compiled iOS service/host file is absent or symlinked")
    before = [p.read_text(encoding="utf-8") for p in paths]
    after = [patch_bridge(before[0]), patch_host(before[1])]
    for original, updated, path in zip(before, after, paths):
        if original != updated:
            path.write_text(updated, encoding="utf-8")
    print("[PASS] V189 actual auth admission/connect/XPC send/response/timeout traced in host diagnostics")
    print("[SAFE] no Apple secrets, no forced service restart, no certificate or UI changes")
    print("[UNVERIFIED] device service readiness and 2FA require signed iPhone testing")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v189_auth_bridge_trace.py <LiveContainer>")
    apply(Path(sys.argv[1]))
