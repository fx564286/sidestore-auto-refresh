#!/usr/bin/env python3
"""V189 login-entry recovery: show credential UI without waiting on SideStore XPC.

The Apple ID/password are held only in transient view/auth-store memory until the
matching credential prompt from the existing SideSign session arrives. They are
not placed in UserDefaults, Keychain, diagnostics, or the initial authBegin RPC.
The backend alone owns authentication and 2FA; no fake login completion.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V189_VISIBLE_LOGIN_ENTRY"
REL = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")


def once(src: str, before: str, after: str, label: str) -> str:
    count = src.count(before)
    if count != 1:
        raise ValueError(f"visible-login {label}: expected 1 anchor, found {count}")
    return src.replace(before, after, 1)


def patch(src: str) -> str:
    if MARK in src:
        if src.count(MARK) != 1 or "beginWithCredentials" not in src or (
                "auth.begin()" in src[src.index("struct V3SignInView: View {"):].split(
                    "\nstruct ", 1)[0]):
            raise ValueError("visible-login patch is partial")
        return src
    if "SCARLET_V189_CANCEL_INTENT_PER_SESSION" not in src:
        raise ValueError("V189 retained auth session and cancel-intent required")
    src = once(src,
        "    private var promptResponseGeneration: UInt64 = 0\n",
        "    private var promptResponseGeneration: UInt64 = 0\n"
        "    // " + MARK + ": one-shot credentials, memory-only until exact service prompt.\n"
        "    private var queuedLogin: (sessionID: String, appleID: String, password: String)?\n",
        "one-shot memory-only credential storage")
    src = once(src,
        "    var canBegin: Bool {\n",
        """    func beginWithCredentials(appleID: String, password: String) {
        guard canBegin else { return }
        let normalized = appleID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !normalized.isEmpty, !password.isEmpty else { return }
        queuedLogin = nil
        begin()
        // begin() schedules the actual XPC request on the next actor turn.
        // No credentials ever travel in authBegin; wait for the exact prompt.
        if state == "working", let session { queuedLogin = (session, normalized, password) }
    }

    var canBegin: Bool {
""",
        "explicit user-owned credential start")
    src = once(src,
        "    private func run(sessionID requestedSession: String) async {\n",
        """    private func run(sessionID requestedSession: String) async {
        defer {
            // Cancel/timeouts cannot retain a password for a future session.
            if queuedLogin?.sessionID == requestedSession { queuedLogin = nil }
        }
""",
        "release queued secret at auth end")
    src = once(src,
        '    func cancel() {\n        guard !(state == "resultUnknown" && session == nil) else {\n',
        '    func cancel() {\n        queuedLogin = nil\n'
        '        guard !(state == "resultUnknown" && session == nil) else {\n',
        "clear pending secret on cancel")
    start = src.index("    private func apply(_ reply: [String: Any]) {",
                      src.index("final class V3AuthStore: ObservableObject {"))
    stop = src.index("    func answer(promptID: String, answer: [String: String])", start)
    method = src[start:stop]
    method = once(method,
        '        if state == "completed" {\n',
        """        // Only the session-owned SideStore credentials prompt can consume the
        // prepared password. An unrelated prompt or stale status never receives it.
        if state == "awaitingPrompt",
           let currentPrompt = prompt,
           currentPrompt["kind"] as? String == "credentials",
           let promptID = currentPrompt["id"] as? String, !promptID.isEmpty,
           let fields = currentPrompt["fields"] as? [[String: Any]],
           fields.contains(where: { $0["key"] as? String == "appleID" }),
           fields.contains(where: { $0["key"] as? String == "password" }),
           let queued = queuedLogin, queued.sessionID == session, !isCancelling {
            queuedLogin = nil
            answer(promptID: promptID,
                   answer: ["appleID": queued.appleID, "password": queued.password])
        }
        if isTerminal { queuedLogin = nil }
        if state == "completed" {
""",
        "forward once on exact live SideSign credentials prompt")
    src = src[:start] + method + src[stop:]
    ui_start = src.index("struct V3SignInView: View {")
    ui_stop = src.find("\nstruct ", ui_start + 1)
    if ui_stop < 0:
        raise ValueError("following SwiftUI struct not found")
    ui = src[ui_start:ui_stop]
    ui = once(ui,
        "    @ObservedObject private var auth = V3AuthStore.shared\n",
        "    @ObservedObject private var auth = V3AuthStore.shared\n"
        "    @State private var showCredentialEntry = true\n"
        "    @State private var preparedAppleID = \"\"\n"
        "    @State private var preparedPassword = \"\"\n",
        "sign-in view memory-only input state")
    # Runs after the V185 host-owned authentication session overlay.
    entry = """                if showCredentialEntry && auth.canBegin && !auth.isSignedIn {
                    TextField("Apple ID", text: $preparedAppleID)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textContentType(.username)
                        .keyboardType(.emailAddress)
                    SecureField("Password", text: $preparedPassword)
                        .textContentType(.password)
                    Button("로그인 및 2FA 진행") {
                        let appleID = preparedAppleID
                        let password = preparedPassword
                        preparedAppleID = ""
                        preparedPassword = ""
                        showCredentialEntry = false
                        auth.beginWithCredentials(appleID: appleID, password: password)
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(preparedAppleID.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ||
                              preparedPassword.isEmpty)
                    Text("Apple이 인증 코드를 요청하면 이 화면에서 6자리 코드를 입력합니다.")
                        .font(.footnote)
                        .foregroundColor(.secondary)
                }
"""
    ui = once(ui, "                if auth.isSignedIn {\n",
              entry + "                if auth.isSignedIn {\n",
              "visible credential form on entering Sign In")
    # Do not show a duplicate Begin Sign In button next to the open form.
    ui = once(ui, '                if auth.state == "idle" {\n',
              '                if auth.state == "idle" && !showCredentialEntry {\n',
              "avoid duplicate start control")
    count = ui.count("auth.begin()")
    if count < 3 or count > 7:
        raise ValueError(f"unexpected interactive login actions: {count}")
    ui = ui.replace("auth.begin()", "showCredentialEntry = true")
    # Changing tabs must not silently cancel the host-owned Apple/2FA session.
    ui = once(ui,
        """        .onDisappear {
            auth.cancel()
            auth.clearPreviousFailure()
            // The root auth-event observer owns certificate-readiness
""",
        """        .onDisappear {
            preparedAppleID = ""
            preparedPassword = ""
            showCredentialEntry = false
            // Do not cancel SideStore on navigation; only explicit Cancel owns it.
            // The root auth-event observer owns certificate-readiness
""",
        "preserve authentication across navigation")
    src = src[:ui_start] + ui + src[ui_stop:]
    if patch(src) != src:
        raise ValueError("patch is not idempotent")
    return src


def apply(root: Path) -> None:
    target = root / REL
    if not target.is_file() or target.is_symlink():
        raise ValueError("compiled LiveContainer SwiftUI source missing")
    old = target.read_text(encoding="utf-8")
    updated = patch(old)
    if updated != old:
        target.write_text(updated, encoding="utf-8")
    print("[PASS] V189_VISIBLE_APPLE_ID_PASSWORD_AND_INLINE_2FA")
    print("[PASS] no auto-cancel on navigation; credentials only sent on real prompt")
    print("[UNVERIFIED] Apple sign-in, 2FA and signed iPhone runtime still require device check")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v189_login_entry.py <LiveContainer>")
    apply(Path(sys.argv[1]))
