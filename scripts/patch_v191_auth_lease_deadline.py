#!/usr/bin/env python3
"""V191: bound authBegin's pre-XPC status-authority wait.

Do not release active/unresolved mutation ownership without authoritative
evidence. A 25-second host request deadline must cover acquisition of the
status lease, not just XPC execution after that lease was acquired.

Patch applies only after V189 phase tracing and intentionally does not change
the pinned embedded SideStore code, Apple credentials, provisioning, or UI.
"""
from pathlib import Path
import sys

MARK="SCARLET_V191_AUTH_LEASE_DEADLINE"
BRIDGE=Path("SideStoreSupport/SideStore.swift")
HOST=Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")


def one(text: str, before: str, after: str, label: str) -> str:
    count=text.count(before)
    if count != 1:
        raise ValueError(f"V191 {label}: expected one source anchor, found {count}")
    return text.replace(before, after, 1)


def patch_bridge(s: str) -> str:
    if MARK in s:
        required=(
            "deadline: Date? = nil",
            "private func timeoutStatusLeaseWaiter",
            'traceAuthPhase(operation: operation, phase: "lease_unavailable")',
            'traceAuthPhase(operation: operation, phase: "lease_cancelled")',
            "deadline: requestDeadline",
        )
        if s.count(MARK) != 1 or any(x not in s for x in required):
            raise ValueError("V191 bridge is only partially patched")
        return s
    if "SCARLET_V189_AUTH_TRANSPORT_PHASE_TRACE" not in s:
        raise ValueError("V191 requires V189 bridge trace; source drift")
    s=one(s,
        """    private func acquireStatusLease(ownerID: String,
                                    kind: V3StatusAuthorityLeaseKind,
                                    allowUnresolvedMutation: Bool = false) async throws -> V3StatusWriteTicket {
        try Task.checkCancellation()
""",
        """    // SCARLET_V191_AUTH_LEASE_DEADLINE: do not wait forever for a prior
    // status writer. Expiring a WAITER must never retire the active writer.
    private func acquireStatusLease(ownerID: String,
                                    kind: V3StatusAuthorityLeaseKind,
                                    allowUnresolvedMutation: Bool = false,
                                    deadline: Date? = nil) async throws -> V3StatusWriteTicket {
        try Task.checkCancellation()
        if let deadline, deadline <= Date() {
            throw CombinedFailure(operation: "signIn", stage: .command, code: .timedOut,
                id: ownerID, retryable: false, safeCause: .operationInProgress)
        }
""",
        "lease signature + deadline precheck")
    s=one(s,
        """        let waiterID = UUID().uuidString
        let reservedRevision: UInt64
""",
        """        let waiterID = UUID().uuidString
        // The child task does not change activeLease. On deadline it only
        // removes this request's queued continuation, which is one-shot.
        let leaseDeadlineTask: Task<Void, Never>? = deadline.map { stopAt in
            Task { @MainActor [weak self] in
                let remaining = stopAt.timeIntervalSinceNow
                if remaining > 0 {
                    do {
                        try await Task.sleep(nanoseconds: UInt64(remaining * 1_000_000_000))
                    } catch { return }
                }
                self?.timeoutStatusLeaseWaiter(waiterID)
            }
        }
        defer { leaseDeadlineTask?.cancel() }
        let reservedRevision: UInt64
""",
        "timeout task")
    s=one(s,
        """    private func drainStatusLeaseWaiters() {
        guard statusWriteAuthority.activeLease == nil else { return }
""",
        """    private func timeoutStatusLeaseWaiter(_ waiterID: String) {
        statusLeaseWaiterOrder.remove(waiterID)
        guard let index = statusLeaseWaiters.firstIndex(where: { $0.id == waiterID }) else { return }
        let waiter = statusLeaseWaiters.remove(at: index)
        // No statusWriteAuthority.complete(), retireService() or service restart:
        // another owner's active or unresolved mutation remains authoritative.
        waiter.continuation.resume(throwing: CombinedFailure(
            operation: "signIn", stage: .command, code: .timedOut,
            id: waiter.id, retryable: false, safeCause: .operationInProgress))
    }

    private func drainStatusLeaseWaiters() {
        guard statusWriteAuthority.activeLease == nil else { return }
""",
        "timeout waiter without releasing unrelated owner")
    s=one(s,
        """        if let statusOwnerID, let statusLeaseKind {
            traceAuthPhase(operation: operation, phase: "lease_waiting")
            statusLeaseTicket = try await acquireStatusLease(ownerID: statusOwnerID, kind: statusLeaseKind,
                allowUnresolvedMutation: explicitDirectRecoveryControl)
            traceAuthPhase(operation: operation, phase: "lease_acquired")
            statusLeaseByRequestID[id] = statusLeaseTicket
        }
""",
        """        if let statusOwnerID, let statusLeaseKind {
            traceAuthPhase(operation: operation, phase: "lease_waiting")
            // Fixed, privacy-safe blocker categories: never emit owner IDs.
            if statusWriteAuthority.activeLease?.kind == .snapshot {
                traceAuthPhase(operation: operation, phase: "lease_blocked_snapshot")
            } else if statusWriteAuthority.activeLease?.kind == .mutation {
                traceAuthPhase(operation: operation, phase: "lease_blocked_mutation")
            } else if statusWriteAuthority.hasUnresolvedMutation {
                traceAuthPhase(operation: operation, phase: "lease_blocked_unresolved")
            } else if statusLeaseWaiterOrder.count > 0 {
                traceAuthPhase(operation: operation, phase: "lease_blocked_queue")
            }
            do {
                statusLeaseTicket = try await acquireStatusLease(
                    ownerID: statusOwnerID, kind: statusLeaseKind,
                    allowUnresolvedMutation: explicitDirectRecoveryControl,
                    deadline: requestDeadline)
                traceAuthPhase(operation: operation, phase: "lease_acquired")
                statusLeaseByRequestID[id] = statusLeaseTicket
            } catch {
                if error is CancellationError {
                    traceAuthPhase(operation: operation, phase: "lease_cancelled")
                    throw error
                }
                traceAuthPhase(operation: operation, phase: "lease_unavailable")
                if ["authBegin", "authRetryProvisioning"].contains(operation) {
                    let failure = (error as? CombinedFailure) ?? CombinedFailure.capture(
                        error, operation: "signIn", stage: .command, id: id)
                    throw V3AuthAttemptStartFailurePolicy.confirmedNotDispatched(
                        failure, operation: operation)
                }
                throw error
            }
        }
""",
        "bounded lease acquisition, fail-closed classification and diagnostic")
    if patch_bridge(s) != s:
        raise ValueError("V191 bridge patch is not idempotent")
    return s


PHASES=(
    ('begin.lease_blocked_snapshot','auth.rpc.lease_blocked_snapshot'),
    ('begin.lease_blocked_mutation','auth.rpc.lease_blocked_mutation'),
    ('begin.lease_blocked_unresolved','auth.rpc.lease_blocked_unresolved'),
    ('begin.lease_blocked_queue','auth.rpc.lease_blocked_queue'),
    ('begin.lease_unavailable','auth.rpc.lease_unavailable'),
    ('begin.lease_cancelled','auth.rpc.lease_cancelled'),
)


def patch_host(s: str) -> str:
    if MARK in s:
        if s.count(MARK) != 1 or 'auth.rpc.lease_unavailable' not in s:
            raise ValueError("V191 host logger incomplete")
        return s
    if "SCARLET_V189_AUTH_TRANSPORT_PHASE_TRACE" not in s:
        raise ValueError("V191 requires V189 log allowlist")
    extra_cases=''.join(
        f'    case trace{i+15} = "{event}"\n'
        for i,(_,event) in enumerate(PHASES))
    s=one(s,
        '    case trace14 = "auth.cancel_rpc.timed_out"\n',
        '    case trace14 = "auth.cancel_rpc.timed_out"\n'
        '    // '+MARK+': no session IDs or credentials in log events.\n'
        +extra_cases,
        "fixed logger event allowlist")
    mappings=''.join(
        f'            case "{phase}": ScarletV183HostLog.record(.trace{i+15})\n'
        for i,(phase,_) in enumerate(PHASES))
    s=one(s,
        '            case "begin.lease_waiting": ScarletV183HostLog.record(.trace1)\n',
        '            case "begin.lease_waiting": ScarletV183HostLog.record(.trace1)\n'+mappings,
        "host event mapping")
    if patch_host(s) != s:
        raise ValueError("V191 host patch is not idempotent")
    return s


def apply(root: Path) -> None:
    paths=(root/BRIDGE,root/HOST)
    if any(not p.is_file() or p.is_symlink() for p in paths):
        raise ValueError("compiled host bridge unavailable")
    before=[p.read_text(encoding="utf8") for p in paths]
    after=[patch_bridge(before[0]),patch_host(before[1])]
    for p,old,new in zip(paths,before,after):
        if old!=new: p.write_text(new,encoding="utf8")
    print("[PASS] V191 bounded host auth lease admission before XPC connect")
    print("[SAFE] Existing active mutation/lease and App Group remain unchanged")
    print("[UNVERIFIED] Apple login and actual iPhone runtime need on-device test")


if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v191_auth_lease_deadline.py <LiveContainer>")
    apply(Path(sys.argv[1]))
