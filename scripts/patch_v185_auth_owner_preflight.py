#!/usr/bin/env python3
"""V185: keep one host-owned authentication session across navigation, and
fail fast on the App Group entitlement removed by prior force-sign output.
Do not change Apple credentials, SideStore server state or any Liquid Glass UI.
The service decides login; a local entitlement check never claims success.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V185_AUTH_HOST_OWNER_PREFLIGHT"
REL = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")


def once(src, before, after, name):
    found = src.count(before)
    if found != 1:
        raise ValueError(f"V185 {name}: expected one anchor; found {found}")
    return src.replace(before, after, 1)


def patch(src: str) -> str:
    if MARK in src:
        required = ("static let shared = V3AuthStore()",
                    "@ObservedObject private var auth = V3AuthStore.shared",
                    "auth.begin_dispatched", "auth.begin_accepted",
                    "auth.begin_request_failed", "auth.entitlement_app_group_missing",
                    "requestDeadline: Date().addingTimeInterval(25)")
        if src.count(MARK) != 1 or any(v not in src for v in required):
            raise ValueError("V185 auth ownership/preflight patch incomplete")
        return src
    if "SCARLET_V184_AUTH_CANCEL_OUTCOMES" not in src:
        raise ValueError("V185 requires V184 instrumentation and V183 host journal")
    src = once(src,
        '    case authCancelTransportFailed = "auth.cancel_transport_failed"\n',
        '    case authCancelTransportFailed = "auth.cancel_transport_failed"\n'
        '    case authBeginDispatched = "auth.begin_dispatched"\n'
        '    case authBeginAccepted = "auth.begin_accepted"\n'
        '    case authBeginRequestFailed = "auth.begin_request_failed"\n'
        '    case authAppGroupMissing = "auth.entitlement_app_group_missing"\n',
        "allowlisted diagnostic event names")
    src = once(src,
        "final class V3AuthStore: ObservableObject {\n",
        """final class V3AuthStore: ObservableObject {
    // SCARLET_V185_AUTH_HOST_OWNER_PREFLIGHT: the sign-in view is transient,
    // but the authenticated session and pending Apple/2FA prompts are not.
    // One actor-isolated host-owned store keeps the in-flight request alive
    // when the user navigates to the log viewer or closes a sheet.
    static let shared = V3AuthStore()

    private static var hasRequiredHostAppGroup: Bool {
        guard let task = SecTaskCreateFromSelf(kCFAllocatorDefault) else { return false }
        guard let groups = SecTaskCopyValueForEntitlement(
            task, "com.apple.security.application-groups" as CFString, nil
        ) as? [String] else { return false }
        return groups.contains { !$0.isEmpty }
    }
""",
        "shared host owner and installed entitlements")
    src = once(src,
        "    func begin() {\n        guard canBegin else { return }\n        task?.cancel()\n",
        """    func begin() {
        guard canBegin else { return }
        // Detect actual OS-granted rights, never infer grants from an XML
        // profile or the fact that a USB installer returned 100%.
        // This failure must be repaired at Apple App ID/profile signing time.
        guard Self.hasRequiredHostAppGroup else {
            state = "failed"
            message = "This Scarlet Crystal install has no Apple App Group entitlement. SideStore login and shared service cannot be trusted in this build. Restore App Groups in Apple provisioning, re-sign all four bundles, then upgrade without deleting the installed app."
            ScarletV183HostLog.record(.authAppGroupMissing)
            return
        }
        task?.cancel()
""",
        "preflight in user-initiated sign-in")
    src = once(src,
        """            let reply = try await V3ServiceBridge.shared.request(operation: "authBegin",
                target: requestedSession,
                payload: ["session": requestedSession, "sessionDeadline": sessionDeadline])
""",
        """            // Time-bound only the session-start RPC; Apple 2FA and account
            // prompts continue to use the original longer session lifetime.
            ScarletV183HostLog.record(.authBeginDispatched)
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
""",
        "25s bounded authBegin service roundtrip")
    src = once(src,
        """            session = id
            try await pollLoop(id: id, sessionDeadline: sessionDeadline)
""",
        """            session = id
            ScarletV183HostLog.record(.authBeginAccepted)
            try await pollLoop(id: id, sessionDeadline: sessionDeadline)
""",
        "session ownership transition")
    src = once(src,
        "    @StateObject private var auth = V3AuthStore()\n",
        "    @ObservedObject private var auth = V3AuthStore.shared\n",
        "navigation-safe auth state observer")
    return src


def apply(root: Path):
    path = root / REL
    if not path.is_file() or path.is_symlink():
        raise ValueError("V185 source unavailable")
    original = path.read_text(encoding="utf-8")
    updated = patch(original)
    if patch(updated) != updated:
        raise ValueError("V185 idempotence failed")
    if original != updated:
        path.write_text(updated, encoding="utf-8")
    print("[V185] host-owned auth state retained across view dismissal")
    print("[V185] App Group preflight + bounded authBegin events, no secret logs")
    print("[V185] Apple sign-in and live signing capabilities require device testing")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v185_auth_owner_preflight.py <LiveContainer>")
    apply(Path(sys.argv[1]))
