#!/usr/bin/env python3
"""V98: privacy-safe Apple GrandSlam failure provenance and bounded -80046 sign-in.

Applies only after existing NRG GSA V1/V2/V3 and SignInOperation integration.
Does not change credential storage, Anisette, Apple identity, network payloads,
or replay any authentication/OTP request. Rejects upstream drift.
"""
from __future__ import annotations
import argparse
from pathlib import Path

AUTH_REL = Path("Dependencies/SideSign/Sources/DeveloperPortal/Authentication.swift")
SIGN_REL = Path("SideStore/Core/Operations/StandaloneOperations/SignInOperation.swift")
AUTH_MARKER = "SCARLET_V98_GSA_PHASE_TRACE"
SIGN_MARKER = "SCARLET_V98_80046_TERMINAL"
AUTH_OLD = r'''        let errorCode = status["ec"] as? Int ?? 0
        if errorCode != 0 {
            let errorDesc = status["em"] as? String
            debugLog("[SideSign] Auth endpoint returned error code \(errorCode): \(errorDesc ?? "No error message")")
'''
AUTH_NEW = r'''        let errorCode = status["ec"] as? Int ?? 0
        // SCARLET_V98_GSA_PHASE_TRACE: one bounded, privacy-safe provenance
        // event per real GSA response. Do not log auth response/body/messages,
        // Anisette values, Apple ID, tokens, headers, SRP proofs or OTP codes.
        let rawOperation = requestParameters["o"] as? String ?? "other"
        let safeOperation = ["init", "complete", "apptokens"].contains(rawOperation)
            ? rawOperation : "other"
        let anisetteFamily: String
        if anisetteData.clientInfo.contains("<Windows;") {
            anisetteFamily = "windows"
        } else if anisetteData.clientInfo.contains("<Android;") {
            anisetteFamily = "android"
        } else if anisetteData.clientInfo.contains("<Mac") {
            anisetteFamily = "mac"
        } else {
            anisetteFamily = "other"
        }
        let sentClientInfo = request.value(forHTTPHeaderField: "X-MMe-Client-Info") ?? ""
        let sentFamily: String
        if sentClientInfo.contains("<Windows;") {
            sentFamily = "windows"
        } else if sentClientInfo.contains("<Android;") {
            sentFamily = "android"
        } else if sentClientInfo.contains("<Mac") {
            sentFamily = "mac"
        } else {
            sentFamily = "other"
        }
        debugLog("[SCARLET_V98_GSA] operation=\(safeOperation) http=\(statusCode) apple_ec=\(errorCode) anisette_family=\(anisetteFamily) sent_family=\(sentFamily)")
        if errorCode != 0 {
            let errorDesc = status["em"] as? String
            // Do not surface Apple's potentially sensitive response message.
'''
SIGN_OLD = "code == 503 || code == 429 || code == -80045 || code == -22411"
SIGN_NEW = "code == 503 || code == 429 || code == -80045 || code == -80046 || code == -22411"
SIGN_ANCHOR = "                if case ServerError.underlyingError(let code, _) = error,"
SIGN_INSERT = ("                // SCARLET_V98_80046_TERMINAL: unknown Apple server policy;\n"
               "                // do not loop credentials, clear accounts or auto-replay SRP.\n" + SIGN_ANCHOR)

def patch_auth(source: str) -> str:
    for marker in ("NRG_GSA_RECOVERY_V1", "NRG_GSA_HTTP_STATUS_V2",
                   "NRG_GSA_CLIENT_IDENTITY_V3"):
        if marker not in source:
            raise ValueError("Required previously reviewed GSA integration missing")
    if AUTH_MARKER in source:
        if source.count(AUTH_MARKER) != 1 or AUTH_NEW not in source or AUTH_OLD in source:
            raise ValueError("Partial or drifted V98 auth patch")
        return source
    if source.count(AUTH_OLD) != 1:
        raise ValueError("Unexpected GSA response decoder: expected one anchor")
    return source.replace(AUTH_OLD, AUTH_NEW, 1)

def patch_signin(source: str) -> str:
    if "NRG_GSA_RECOVERY_V1" not in source or "V3_AUTH_FAILURE_PRESERVES_ACCOUNT_STATE_V1" not in source:
        raise ValueError("Previously reviewed sign-in lifecycle integration missing")
    if "AuthManager.shared.signOut()" in source:
        raise ValueError("Destructive sign-out regressed; fail closed")
    if SIGN_MARKER in source:
        if source.count(SIGN_MARKER) != 1 or source.count(SIGN_NEW) != 3 or SIGN_OLD in source:
            raise ValueError("Partial or drifted V98 signin patch")
        return source
    if source.count(SIGN_OLD) != 3 or source.count(SIGN_ANCHOR) < 3:
        raise ValueError("Unexpected V1 sign-in branches; do not rewrite")
    source = source.replace(SIGN_OLD, SIGN_NEW)
    return source.replace(SIGN_ANCHOR, SIGN_INSERT, 1)

def apply(root: Path, check: bool = False) -> None:
    paths = (root / AUTH_REL, root / SIGN_REL)
    if any(not path.is_file() or path.is_symlink() for path in paths):
        raise ValueError("Expected two regular embedded SideStore files")
    before = tuple(path.read_text(encoding="utf-8") for path in paths)
    after = (patch_auth(before[0]), patch_signin(before[1]))
    if check and before != after:
        raise ValueError("V98 patch not yet installed")
    if not check:
        # Check all anchors before the first write to avoid half-patching.
        for path, original, updated in zip(paths, before, after):
            if updated != original:
                path.write_text(updated, encoding="utf-8")
    print("SCARLET_V98_AUTH_GUARDS_OK", "check" if check else "apply")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("sidestore_root", type=Path)
    parser.add_argument("--check", action="store_true")
    opts = parser.parse_args()
    apply(opts.sidestore_root, opts.check)
