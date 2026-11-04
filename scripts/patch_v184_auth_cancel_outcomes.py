#!/usr/bin/env python3
"""V184: Record the authoritative cancellation outcome in the auth store.

The V183 UI-only .onChange observer can disappear when the sign-in view is
dismissed. No credentials, session IDs, error payloads or account data are
written to the diagnostic log. Preserve the original authentication logic and
the user's complete UI / Liquid Glass design.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V184_AUTH_CANCEL_OUTCOMES"
REL = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")


def once(source: str, before: str, after: str, name: str) -> str:
    count = source.count(before)
    if count != 1:
        raise ValueError(f"V184 {name}: expected exactly one anchor, found {count}")
    return source.replace(before, after, 1)


def patch(source: str) -> str:
    if MARK in source:
        if (source.count(MARK) != 1
                or source.count("ScarletV183HostLog.record(.authCancelWatchdog)") != 1
                or source.count("ScarletV183HostLog.record(.authCancelTransportFailed)") != 1
                or source.count("cancellationConfirmed ? .authCancelTerminal : .authCancelUnconfirmed") != 1):
            raise ValueError("V184 auth cancellation instrumentation is incomplete")
        return source

    if ("SCARLET_V183_HOST_LOG_FALLBACK" not in source
            or "SCARLET_V182_P00_AUTH_CANCEL_LIVENESS" not in source):
        raise ValueError("V184 requires V182 cancellation + V183 host journal")

    source = once(
        source,
        '    case authCancelRequested = "auth.cancel_requested"\n',
        '    case authCancelRequested = "auth.cancel_requested"\n'
        f'    // {MARK}: host-owned terminal evidence, independent of view lifetime.\n'
        '    case authCancelTerminal = "auth.cancel_terminal"\n'
        '    case authCancelUnconfirmed = "auth.cancel_unconfirmed"\n'
        '    case authCancelWatchdog = "auth.cancel_watchdog"\n'
        '    case authCancelTransportFailed = "auth.cancel_transport_failed"\n',
        "allowlisted event names")

    # The watchdog is not evidence that a remote session was cancelled.
    source = once(
        source,
        '            cancellationWasAttempted = true\n'
        '            state = "resultUnknown"\n'
        '            message = "SideStore has not confirmed cancellation.',
        '            cancellationWasAttempted = true\n'
        '            state = "resultUnknown"\n'
        '            ScarletV183HostLog.record(.authCancelWatchdog)\n'
        '            message = "SideStore has not confirmed cancellation.',
        "20-second UI watchdog")

    # A service completion, a terminal failure or no session at all are
    # distinguishable from a service reply that never proves completion.
    source = once(
        source,
        '                cancellationConfirmed = oldSession == nil || serverTerminal\n'
        '                cancellationWasAttempted = !cancellationConfirmed\n',
        '                cancellationConfirmed = oldSession == nil || serverTerminal\n'
        '                cancellationWasAttempted = !cancellationConfirmed\n'
        '                ScarletV183HostLog.record(\n'
        '                    cancellationConfirmed ? .authCancelTerminal : .authCancelUnconfirmed)\n',
        "server-reported cancellation terminal outcome")

    source = once(
        source,
        '            } catch {\n'
        '                _ = await reconcile(force: true)\n'
        '                guard cancellationEpoch == currentEpoch else { return }\n'
        '                state = "resultUnknown"\n',
        '            } catch {\n'
        '                _ = await reconcile(force: true)\n'
        '                guard cancellationEpoch == currentEpoch else { return }\n'
        '                state = "resultUnknown"\n'
        '                ScarletV183HostLog.record(.authCancelTransportFailed)\n',
        "transport failure without terminal confirmation")
    return source


def apply(root: Path) -> None:
    target = root / REL
    if not target.is_file() or target.is_symlink():
        raise ValueError("V184 host auth source missing")
    old = target.read_text(encoding="utf-8")
    updated = patch(old)
    if patch(updated) != updated:
        raise ValueError("V184 patch is not idempotent")
    if updated != old:
        target.write_text(updated, encoding="utf-8")
    print("[V184] host logs cancellation terminal, unconfirmed, timeout and transport errors")
    print("[V184] authentication and Liquid Glass behavior preserved")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v184_auth_cancel_outcomes.py <LiveContainer>")
    apply(Path(sys.argv[1]))
