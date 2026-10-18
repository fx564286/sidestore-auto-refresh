#!/usr/bin/env python3
"""V46 JIT repair: preserve validated external JIT, recover absent helpers via local debugger.

Applied after V43/V45 to pinned embedded SideStore sources. Never report JIT
activation unless the selected debugApp / SideJIT operation actually completes.
"""
from pathlib import Path
import sys

MARK = "NRG_V46_JIT_RECOVERY"
MANAGER = Path("SideStore/Core/JIT/SideJITManager.swift")
OPERATION = Path("SideStore/Core/Operations/StandaloneOperations/EnableJITOperation.swift")

def once(s: str, old: str, new: str, label: str) -> str:
    count = s.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor, found {count}")
    return s.replace(old, new, 1)

def patch_manager(s: str) -> str:
    if MARK in s:
        return s
    if "NRG_V43_DNSSD_FAIL_CLOSED" not in s or "NRG_V44: no server; skip trigger" not in s:
        raise RuntimeError("JIT manager V43/V44 guards missing")
    # An unresolved .local hostname is not a routable HTTP endpoint.
    old = '''                return resolvedURL
            }
        }
        
        debugLog("[SideJITManager] resolveAddressIfNeeded: default raw host'''
    new = '''                return resolvedURL
            }
            // NRG_V46_JIT_RECOVERY: unresolved .local names must not be returned as valid servers.
            return nil
        }
        
        debugLog("[SideJITManager] resolveAddressIfNeeded: default raw host'''
    s = once(s, old, new, ".local fail-closed")
    # Protect JIT triggering against non-HTTP URL input.
    old = '''        guard !SJSURL.isEmpty else {
            debugLog("[SideJITManager] NRG_V44: no server; skip trigger")
            return
        }
        guard let url = URL(string: "\\(SJSURL)/re/") else {'''
    new = '''        guard !SJSURL.isEmpty else {
            debugLog("[SideJITManager] NRG_V44: no server; skip trigger")
            return
        }
        guard let baseURL = URL(string: SJSURL),
              let scheme = baseURL.scheme?.lowercased(),
              ["http", "https"].contains(scheme), baseURL.host != nil else {
            debugLog("[SideJITManager] NRG_V46_JIT_RECOVERY: invalid server URL; trigger skipped")
            return
        }
        guard let url = URL(string: "\\(SJSURL)/re/") else {'''
    s = once(s, old, new, "trigger URL validation")
    return s

def patch_operation(s: str) -> str:
    if MARK in s:
        return s
    old = '''            guard let serverURL = URL(string: sideJITURLString) else {
                throw OperationError.unableToConnectSideJIT
            }'''
    new = '''            // NRG_V46_JIT_RECOVERY: missing optional helper must not prevent the
            // pre-existing paired-device debugger from being attempted.
            guard !sideJITURLString.isEmpty,
                  let serverURL = URL(string: sideJITURLString),
                  let scheme = serverURL.scheme?.lowercased(),
                  ["http", "https"].contains(scheme), serverURL.host != nil else {
                self.debugLog("[NRG_JIT] external server unavailable; trying local paired debugger")
                try await debugApp(targetBundleId)
                self.debugLog("[NRG_JIT] local debugger returned; verify target JIT on device")
                return
            }'''
    s = once(s, old, new, "empty/unusable server fallback")
    old = '''            } catch {
                if let serverError = error as? SideJITServerErrorType {'''
    new = '''            } catch {
                if let networkError = error as? URLError {
                    switch networkError.code {
                    case .timedOut, .cannotFindHost, .cannotConnectToHost,
                         .networkConnectionLost, .notConnectedToInternet, .dnsLookupFailed:
                        self.debugLog("[NRG_JIT] SideJIT transport failed; trying local paired debugger: \\(networkError.code)")
                        try await debugApp(targetBundleId)
                        self.debugLog("[NRG_JIT] local debugger returned; verify target JIT on device")
                        return
                    default:
                        break
                    }
                }
                if let serverError = error as? SideJITServerErrorType {'''
    s = once(s, old, new, "network failure fallback")
    old = '''    let (data, _) = try await URLSession.shared.data(from: fullURL)

    guard let dataString = String(data: data, encoding: .utf8) else {'''
    new = '''    var request = URLRequest(url: fullURL)
    request.timeoutInterval = 8
    let (data, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
        let status = (response as? HTTPURLResponse)?.statusCode ?? 0
        debugLog("[NRG_JIT] SideJIT returned non-success HTTP status: \\(status)")
        throw SideJITServerErrorType.other("SideJITServer HTTP \\(status)")
    }

    guard let dataString = String(data: data, encoding: .utf8) else {'''
    s = once(s, old, new, "verify JIT API response status")
    return s

def main(root: Path) -> None:
    pending = []
    for relative, fn in ((MANAGER, patch_manager), (OPERATION, patch_operation)):
        target = root / relative
        initial = target.read_text(encoding="utf-8")
        output = fn(initial)
        if MARK not in output or fn(output) != output:
            raise RuntimeError(f"JIT patch validation failed: {relative}")
        pending.append((target, initial, output))
    for path, before, after in pending:
        if after != before:
            path.write_text(after, encoding="utf-8")
        print(f"[PASS] V46 JIT repair: {path.relative_to(root)}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v46_jit_recovery.py <embedded-sidestore-root>")
    main(Path(sys.argv[1]))
