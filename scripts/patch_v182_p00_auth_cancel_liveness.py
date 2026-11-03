#!/usr/bin/env python3
"""P00 authCancel liveness: do not await a cancelled non-terminating sign-in task.

After a bounded, correlated cancellation request, only an actual terminal
SideStore reply can confirm completion. The UI watchdog never fabricates
success and retains the exact session for explicit retry. Glass is untouched.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V182_P00_AUTH_CANCEL_LIVENESS"
HOST = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")


def once(src: str, before: str, after: str, name: str) -> str:
    n = src.count(before)
    if n != 1:
        raise ValueError(f"P00 auth cancel {name}: expected 1 anchor, found {n}")
    return src.replace(before, after, 1)


def transform_cancel_method(method: str) -> str:
    required = ('await oldTask?.value', 'operation: "authCancel"',
                'cancellationConfirmed = true', 'isCancelling = false')
    for token in required:
        if token not in method:
            raise ValueError("P00 auth cancel predecessor changed: " + token)
    if method.count("await oldTask?.value") != 2:
        raise ValueError("P00 auth cancel expected exactly two unbounded oldTask waits")
    method = once(method,
        "        let oldTask = task\n        let oldSession = session\n        task?.cancel()\n",
        '''        let oldSession = session
        task?.cancel()
        // SCARLET_V182_P00_AUTH_CANCEL_LIVENESS: only the service owns
        // terminal confirmation. A cancelled task may ignore cancellation,
        // so its Task.value must never keep this UI in Cancelling forever.
        cancellationEpoch &+= 1
        let currentEpoch = cancellationEpoch
        Task { @MainActor in
            try? await Task.sleep(nanoseconds: 20_000_000_000)
            guard cancellationEpoch == currentEpoch && isCancelling else { return }
            // This is a UI timeout, NOT a backend-cancel confirmation.
            cancellationEpoch &+= 1
            isCancelling = false
            cancellationConfirmed = false
            cancellationWasAttempted = true
            state = "resultUnknown"
            message = "SideStore has not confirmed cancellation. The session remains active or unknown; retry cancellation after checking the service."
            prompt = nil
            promptSubmitting = false
            task = nil
        }
''',
        "epoch and watchdog")
    method = once(method,
        'terminalReply = try await V3ServiceBridge.shared.request(operation: "authCancel", target: oldSession)',
        '''terminalReply = try await V3ServiceBridge.shared.request(
                        operation: "authCancel", target: oldSession,
                        requestDeadline: Date().addingTimeInterval(15))
                    guard cancellationEpoch == currentEpoch else { return }''',
        "deadline for exact session cancellation")
    # Removing Task.value waits avoids waiting on a task blocked inside Apple
    # authentication. Cancellation is instead confirmed by the SideStore reply.
    method = method.replace("                await oldTask?.value\n", "")
    method = once(method,
        "                await reconcile(force: true)\n                cancellationConfirmed = true\n                cancellationWasAttempted = false\n                if !signedIn, terminalReply == nil {",
        '''                _ = await reconcile(force: true)
                guard cancellationEpoch == currentEpoch else { return }
                let serverTerminal = ["cancelled", "completed", "failed",
                                      "timedOut", "promptExpired"].contains(
                    terminalReply?["state"] as? String ?? "")
                cancellationConfirmed = oldSession == nil || serverTerminal
                cancellationWasAttempted = !cancellationConfirmed
                if !cancellationConfirmed {
                    state = "resultUnknown"
                    message = "SideStore returned no confirmed terminal cancellation. Retry cancellation after checking the service."
                } else if !signedIn, terminalReply == nil {''',
        "terminal evidence, not optimistic success")
    method = once(method,
        '''            } catch {
                await reconcile(force: true)
                state = "resultUnknown"
''',
        '''            } catch {
                _ = await reconcile(force: true)
                guard cancellationEpoch == currentEpoch else { return }
                state = "resultUnknown"
''',
        "non-blocking catch and stale-epoch guard")
    method = once(method,
        '''            task = nil
            isCancelling = false
''',
        '''            task = nil
            isCancelling = false
            cancellationEpoch &+= 1
''',
        "mark watchdog superseded by terminal UI outcome")
    if "await oldTask?.value" in method:
        raise ValueError("P00 auth cancel still waits on an unbounded old task")
    return method


def patch(src: str) -> str:
    if MARK in src:
        if src.count(MARK) != 1 or "requestDeadline: Date().addingTimeInterval(15)" not in src:
            raise ValueError("P00 auth cancel patch incomplete")
        return src
    start_class = src.find("final class V3AuthStore: ObservableObject {")
    if start_class < 0 or "V3AuthCancellationRetryPolicy" not in src:
        raise ValueError("P00 expected original V3 authentication store")
    before_next = src.find("\nstruct V3SignInLink: View", start_class)
    start = src.find("    func cancel() {", start_class, before_next)
    if start < 0 or before_next < 0:
        raise ValueError("P00 canonical cancellation function not found")
    end = src.find("\n    }\n}\n", start, before_next)
    if end < 0:
        raise ValueError("P00 auth cancellation class closure changed")
    end += len("\n    }")
    body = src[start:end]
    src = src[:start] + transform_cancel_method(body) + src[end:]
    src = once(src,
        "    private var promptResponseGeneration: UInt64 = 0\n",
        "    private var promptResponseGeneration: UInt64 = 0\n"
        "    private var cancellationEpoch: UInt64 = 0\n",
        "cancellation generation in authenticated store")
    return src


def apply(root: Path):
    path = root / HOST
    if not path.is_file() or path.is_symlink():
        raise ValueError("P00 auth source unavailable: " + str(path))
    before = path.read_text(encoding="utf-8")
    after = patch(before)
    if patch(after) != after:
        raise ValueError("P00 auth cancellation patch not idempotent")
    if before != after:
        path.write_text(after, encoding="utf-8")
    print("[P00_AUTH] bounded session cancel, no unbounded oldTask wait, unknown-safe timeout")
    print("[UNVERIFIED] actual SideStore XPC and iPhone login cancellation")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v182_p00_auth_cancel_liveness.py <LiveContainer>")
    apply(Path(sys.argv[1]))
