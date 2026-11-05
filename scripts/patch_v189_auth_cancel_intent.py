#!/usr/bin/env python3
"""Correlate user cancellation with a pending authBegin session even after watchdog.

V186 relied on isCancelling at the instant a delayed RPC throws; a 20-second
watchdog could reset isCancelling before the 25-second RPC timeout, logging
'auth.begin_request_failed' for an intentional cancel. Keep a per-session
cancellation-intent set until the exact RPC resolves. This is diagnostic-only:
no assertion that Apple's server terminated the session.
"""
from pathlib import Path
import sys

REL=Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
MARK="SCARLET_V189_CANCEL_INTENT_PER_SESSION"

def once(text, old, new, label):
    if text.count(old)!=1:
        raise ValueError(f"V189 auth {label}: expected one anchor, found {text.count(old)}")
    return text.replace(old,new,1)

def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or "authBeginUserCancellationSessions.remove(requestedSession)" not in s:
            raise ValueError("V189 auth partial")
        return s
    if "SCARLET_V186_AUTH_BEGIN_OUTCOME" not in s:
        raise ValueError("V186 cancellation diagnostics required")
    s=once(s,
        "    private var authBeginPendingSessionID: String?\n",
        "    private var authBeginPendingSessionID: String?\n"
        f"    // {MARK}: preserve user cancellation after local watchdog resets state.\n"
        "    private var authBeginUserCancellationSessions: Set<String> = []\n",
        "per-request intent storage")
    s=once(s,
        "        let oldSession = session\n        task?.cancel()\n",
        "        let oldSession = session\n"
        "        if let pending = authBeginPendingSessionID {\n"
        "            authBeginUserCancellationSessions.insert(pending)\n"
        "        }\n"
        "        task?.cancel()\n",
        "cancel marks pending authBegin before cancelling Task")
    start=s.index("    private func run(sessionID requestedSession: String) async {")
    stop=s.index("    private func pollLoop(id:",start)
    method=s[start:stop]
    method=once(method,
        '                    requestDeadline: Date().addingTimeInterval(25))\n'
        '                if authBeginPendingSessionID == requestedSession {\n',
        '                    requestDeadline: Date().addingTimeInterval(25))\n'
        '                // The RPC may return after local user cancellation.\n'
        '                // This does not mean Apple or SideStore confirmed cancellation.\n'
        '                if authBeginUserCancellationSessions.contains(requestedSession) {\n'
        '                    throw CancellationError()\n'
        '                }\n'
        '                if authBeginPendingSessionID == requestedSession {\n',
        "late authBegin reply fencing")
    method=once(method,
        "                if isCancelling || Task.isCancelled || error is CancellationError {\n",
        "                let userCancelIntent = authBeginUserCancellationSessions.remove(requestedSession) != nil\n"
        "                if userCancelIntent || isCancelling || Task.isCancelled || error is CancellationError {\n",
        "per-session cancellation classification")
    s=s[:start]+method+s[stop:]
    return s

def apply(root:Path):
    file=root/REL
    if not file.is_file() or file.is_symlink():
        raise ValueError("compiled host Swift source missing")
    original=file.read_text(encoding="utf-8")
    candidate=patch(original)
    if patch(candidate)!=candidate:
        raise ValueError("V189 auth patch non-idempotent")
    if candidate!=original:
        file.write_text(candidate,encoding="utf-8")
    print("[PASS] V189 user cancelled authBegin remains classified locally cancelled after watchdog")
    print("[NOTICE] Server auth cancellation still unverified; Liquid Glass untouched")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v189_auth_cancel_intent.py <LiveContainer>")
    apply(Path(sys.argv[1]))
