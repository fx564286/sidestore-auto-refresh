#!/usr/bin/env python3
"""NRG V50 — send correct current PID and base64 script to StikDebug.

This fixes request construction. It does not manufacture JIT entitlements,
automatically approve StikDebug's confirmation UI, or assert guest JIT success.
Must run after V49 LiveContainer source patches.
"""
from pathlib import Path
import sys

VIEW = Path("LiveContainerSwiftUI/Views/AppList/LCAppListView.swift")
UTILS = Path("LiveContainerSwiftUI/Utilities/LCUtilsExtensions.swift")
MARKER = "NRG_V50_STIKDEBUG_PROTOCOL"


def exactly_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, got {count}")
    return text.replace(old, new, 1)


def patch_view(text: str) -> str:
    """Fix LiveProcess PID URL; V49 already adds URLComponents."""
    if MARKER in text:
        if text.count(MARKER) != 2 or 'Data(script.utf8).base64EncodedString()' not in text:
            raise RuntimeError("partially patched V50 AppList view")
        return text
    if "NRG_V49_PID_SAFE_HANDOFF" not in text:
        raise RuntimeError("V50 requires V49 PID-safe handoff")
    begin = text.index('    func jitLaunch(withPID pid:')
    end = text.index('    func showRunWhenMultitaskAlert()', begin)
    part = text[begin:end]
    part = exactly_once(
        part,
        '                components.scheme = "stikjit"\n',
        '                // '+ MARKER +': prefer current StikDebug scheme for external app.\n'
        '                // Preserve legacy stikjit for a StikDebug guest inside LC.\n'
        '                components.scheme = jitEnabler == .StikJITLC ? "stikjit" : "stikdebug"\n',
        "LiveProcess scheme")
    part = exactly_once(
        part,
        '                    components.queryItems?.append(URLQueryItem(name: "script-data", value: script))',
        '                    components.queryItems?.append(URLQueryItem(name: "script-data", value: Data(script.utf8).base64EncodedString()))',
        "LiveProcess script base64")
    part = exactly_once(
        part,
        '                NSLog("[NRG_V49_PID_SAFE_HANDOFF] target_pid=%d host_id=%@ provider=%@ runtime_jit_unverified=1",',
        '                NSLog("[NRG_V50_STIKDEBUG_PROTOCOL] target_pid=%d host_id=%@ provider=%@ script_wire=base64 runtime_jit_unverified=1",',
        "LiveProcess correlation log")
    return text[:begin] + part + text[end:]


def patch_utils(text: str) -> str:
    """Fix the classic single-host StikDebug route; avoid bundle-ID relaunch."""
    if MARKER in text:
        if text.count(MARKER) != 1 or 'URLQueryItem(name: "pid", value: String(getpid()))' not in text:
            raise RuntimeError("partially patched V50 LCUtilsExtensions")
        return text
    old = '''            var launchURLStr = "stikjit://enable-jit?bundle-id=\\(Bundle.main.bundleIdentifier!)"

            if let script = script, !script.isEmpty {
                launchURLStr += "&script-data=\\(script)"
            }
'''
    new = '''            // NRG_V50_STIKDEBUG_PROTOCOL: target the currently running host PID.
            // Bundle-ID-only requests can relaunch a different PID and lose JIT.
            // StikDebug expects script-data as base64, never raw JavaScript.
            guard let bundleID = Bundle.main.bundleIdentifier else {
                onServerMessage?("V50: LiveContainer bundle ID is unavailable.")
                return false
            }
            var request = URLComponents()
            request.scheme = jitEnabler == .StikJITLC ? "stikjit" : "stikdebug"
            request.host = "enable-jit"
            request.queryItems = [
                URLQueryItem(name: "bundle-id", value: bundleID),
                URLQueryItem(name: "pid", value: String(getpid()))
            ]
            if let script = script, !script.isEmpty {
                request.queryItems?.append(
                    URLQueryItem(name: "script-data", value: Data(script.utf8).base64EncodedString())
                )
            }
            guard let launchRequest = request.url else {
                onServerMessage?("V50: Could not construct StikDebug JIT request.")
                return false
            }
            let launchURLStr = launchRequest.absoluteString
'''
    return exactly_once(text, old, new, "classic host current PID/script protocol")


def main(root: Path) -> None:
    # Validate both patches BEFORE writing either path.
    changes = []
    for path, patch in ((VIEW, patch_view), (UTILS, patch_utils)):
        target = root / path
        before = target.read_text(encoding="utf-8")
        after = patch(before)
        if patch(after) != after:
            raise RuntimeError(f"non-idempotent V50 transform: {path}")
        changes.append((target, before, after))
    for target, before, after in changes:
        if after != before:
            target.write_text(after, encoding="utf-8")
        print(f"[PASS] V50 StikDebug protocol: {target.relative_to(root)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v50_stikdebug_protocol.py <LiveContainer source root>")
    main(Path(sys.argv[1]))
