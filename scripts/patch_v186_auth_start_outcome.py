#!/usr/bin/env python3
"""V186: distinguish user-cancelled authBegin from transport failures.

A request interrupted by its own Task.cancel() must not be logged as a
backend/Apple error. Watch a bounded pending RPC without inferring success.
No identifiers, credentials, 2FA codes, error payloads or profile data
enter the private allowlisted host journal.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V186_AUTH_BEGIN_OUTCOME"
REL = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")


def once(src: str, before: str, after: str, name: str) -> str:
    n = src.count(before)
    if n != 1:
        raise ValueError(f"V186 {name}: expected exactly one source anchor, got {n}")
    return src.replace(before, after, 1)


def patch(src: str) -> str:
    if MARK in src:
        required = (
            'auth.begin_waiting',
            'auth.begin_locally_cancelled',
            'auth.begin_request_failed',
            'auth.begin_accepted',
            'authBeginPendingSessionID',
            'Task.sleep(nanoseconds: 10_000_000_000)',
            'if isCancelling || Task.isCancelled || error is CancellationError',
        )
        if src.count(MARK) != 1 or any(x not in src for x in required):
            raise ValueError("V186 existing instrumentation is incomplete")
        return src
    if "SCARLET_V185_AUTH_HOST_OWNER_PREFLIGHT" not in src:
        raise ValueError("V186 requires V185 retained authentication session")

    src = once(src,
        '    case authBeginRequestFailed = "auth.begin_request_failed"\n',
        '    case authBeginRequestFailed = "auth.begin_request_failed"\n'
        f'    // {MARK}: distinguish local user cancel and unresolved RPC.\n'
        '    case authBeginWaiting = "auth.begin_waiting"\n'
        '    case authBeginLocallyCancelled = "auth.begin_locally_cancelled"\n',
        "allowlisted events")

    src = once(src,
        "    private var session: String?\n"
        "    private var authoritativeActiveAuthenticationSessionID: String?\n",
        "    private var session: String?\n"
        "    // Only tracks the current authBegin RPC, not the Apple 2FA session.\n"
        "    private var authBeginPendingSessionID: String?\n"
        "    private var authoritativeActiveAuthenticationSessionID: String?\n",
        "per-session pending request tracking")

    old = '''            ScarletV183HostLog.record(.authBeginDispatched)
            let reply: [String: Any]
            do {
                reply = try await V3ServiceBridge.shared.request(operation: "authBegin",
                    target: requestedSession,
                    payload: ["session": requestedSession, "sessionDeadline": sessionDeadline],
                    requestDeadline: Date().addingTimeInterval(25))
            } catch {
                ScarletV183HostLog.record(.authBeginRequestFailed)
                throw error
            }
'''
    new = '''            ScarletV183HostLog.record(.authBeginDispatched)
            authBeginPendingSessionID = requestedSession
            // This is a UI indication only: 10 seconds without an RPC reply
            // does NOT prove Apple rejected sign-in or SideStore dropped XPC.
            Task { @MainActor [weak self] in
                try? await Task.sleep(nanoseconds: 10_000_000_000)
                guard let self, self.authBeginPendingSessionID == requestedSession,
                      self.session == requestedSession, !self.isCancelling else { return }
                ScarletV183HostLog.record(.authBeginWaiting)
                self.message = "Waiting for SideStore to respond to sign-in. The start request has a 25-second limit. Keep this screen open unless you want to cancel."
            }
            let reply: [String: Any]
            do {
                reply = try await V3ServiceBridge.shared.request(operation: "authBegin",
                    target: requestedSession,
                    payload: ["session": requestedSession, "sessionDeadline": sessionDeadline],
                    requestDeadline: Date().addingTimeInterval(25))
                if authBeginPendingSessionID == requestedSession {
                    authBeginPendingSessionID = nil
                }
            } catch {
                if authBeginPendingSessionID == requestedSession {
                    authBeginPendingSessionID = nil
                }
                if isCancelling || Task.isCancelled || error is CancellationError {
                    // Cancellation of the local request is not proof that the
                    // SideStore server actually cancelled the Apple session.
                    ScarletV183HostLog.record(.authBeginLocallyCancelled)
                } else {
                    ScarletV183HostLog.record(.authBeginRequestFailed)
                }
                throw error
            }
'''
    # Only patch the actual authBegin method, never provisioning retries.
    start = src.index("    private func run(sessionID requestedSession: String) async {")
    end = src.index("    private func pollLoop(id:", start)
    method = src[start:end]
    method = once(method, old, new, "authentication-start RPC")
    src = src[:start] + method + src[end:]
    return src


def apply(root: Path):
    target = root / REL
    if not target.is_file() or target.is_symlink():
        raise ValueError(f"V186 source missing or symlink: {target}")
    original = target.read_text(encoding="utf-8")
    modified = patch(original)
    if patch(modified) != modified:
        raise ValueError("V186 patch not idempotent")
    if modified != original:
        target.write_text(modified, encoding="utf-8")
    print("[V186] Distinct cancellation vs actual authBegin transport failures")
    print("[V186] 10-second pending feedback; original 25-second RPC deadline unchanged")
    print("[V186] no secret logs; UI design, existing Apple login and signing preserved")
    print("[UNVERIFIED] signed device live login / Apple backend")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v186_auth_start_outcome.py <LiveContainer>")
    apply(Path(sys.argv[1]))
