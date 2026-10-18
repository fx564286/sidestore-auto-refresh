#!/usr/bin/env python3
"""NRG V45: respect SideStore's built-in Local VPN and optional SideJITServer settings.

Patches only the pinned embedded SideStore source; does not change VPN routes,
pairing records, Apple accounts, certificates, or the Refresh transport.
Idempotent and fail-closed on upstream source drift.
"""
from pathlib import Path
import sys

MARK = "NRG_V45_SETTINGS_FIRST"
BOOT = Path("SideStore/AppBootManager.swift")
VIEW = Path("SideStore/Views/Settings/Advanced/JIT/SideJITServerConfigView.swift")

BOOT_OLD = """            if #available(iOS 17, *), !UserDefaults.standard.isSideJITServerEnabled {
                do {
                    try await SideJITManager.shared.isSideJITServerDetected()
                    self.needsSideJITPrompt = true
                } catch {
                    debugLog("[AppBootManager] Cannot find sideJITServer")
                }
            }
            
            if #available(iOS 17, *), UserDefaults.standard.isSideJITServerEnabled {
                await SideJITManager.shared.askForNetwork()
                debugLog("[AppBootManager] SideJITServer Enabled")
            }"""
BOOT_NEW = """            // NRG_V45_SETTINGS_FIRST: do not scan for an optional external helper
            // when the user has disabled it. Local VPN and Refresh are independent.
            if #available(iOS 17, *) {
                if UserDefaults.standard.isSideJITServerEnabled {
                    await SideJITManager.shared.askForNetwork()
                    debugLog("[AppBootManager] SideJITServer trigger finished; JIT not verified")
                } else {
                    debugLog("[AppBootManager] SideJITServer disabled; external discovery skipped")
                }
            }"""

UI_OLD = """            await MainActor.run {
                self.resolvedAddress = serverURL
            }
            await performPing(to: serverURL)"""
UI_NEW = """            // NRG_V45_SETTINGS_FIRST: empty resolution means unavailable,
            // never "Resolving..." forever or a successful Local VPN/JIT.
            guard !serverURL.isEmpty else {
                await MainActor.run {
                    guard self.isServerEnabled else { return }
                    self.resolvedAddress = ""
                    self.connectionStatus = .disconnected(reason: "Server not discovered")
                }
                debugLog("[SideJITConfig] Optional external server unavailable; Local VPN unaffected")
                return
            }
            let stillEnabled = await MainActor.run { self.isServerEnabled }
            guard stillEnabled else { return }
            await MainActor.run { self.resolvedAddress = serverURL }
            await performPing(to: serverURL)"""

def once(s: str, old: str, new: str, label: str) -> str:
    count = s.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one source anchor, found {count}")
    return s.replace(old, new, 1)

def patch_boot(s: str) -> str:
    if MARK in s:
        return s
    return once(s, BOOT_OLD, BOOT_NEW, "boot JIT policy")

def patch_view(s: str) -> str:
    if MARK in s:
        return s
    s = once(s, 'Text("Required for JIT on iOS 17+")',
             'Text("Optional external JIT helper; not required for Local VPN")',
             "JIT explanatory label")
    s = once(s, 'footer: Text("Leave empty to automatically discover SideJITServer on your local network via Bonjour.")',
             'footer: Text("Leave empty to discover an optional external JIT server via Bonjour. Local VPN and app Refresh do not require this server.")',
             "server address explanation")
    s = once(s, 'Text(resolvedAddress.isEmpty ? "Resolving…" : resolvedAddress)',
             'Text(resolvedAddress.isEmpty ? "Not discovered" : resolvedAddress)',
             "unresolved address label")
    s = once(s, UI_OLD, UI_NEW, "UI connection check")
    s = once(s, '''                } else {
                    connectionStatus = .disabled
                }
            }
        }
    }''', '''                } else {
                    connectionStatus = .disabled
                    resolvedAddress = ""
                }
            }
        }
    }''', "disable UI state")
    s = once(s, '''        guard isServerEnabled else {
            connectionStatus = .disabled
            debugLog("[SideJITConfig] refreshServerState: SideJITServer is disabled")''',
             '''        guard isServerEnabled else {
            connectionStatus = .disabled
            resolvedAddress = ""
            debugLog("[SideJITConfig] refreshServerState: SideJITServer is disabled")''',
             "disabled refresh state")
    return s

def main(root: Path) -> None:
    files = [(root / BOOT, patch_boot), (root / VIEW, patch_view)]
    prepared = []
    for f, transform in files:
        before = f.read_text(encoding="utf-8")
        after = transform(before)
        assert MARK in after, f"patch marker missing from {f}"
        assert transform(after) == after, f"non-idempotent patch for {f}"
        prepared.append((f, before, after))
    # Prepare all changes before any write; anchor drift must not half-patch.
    for f, before, after in prepared:
        if after != before:
            f.write_text(after, encoding="utf-8")
        print(f"[PASS] {f.relative_to(root)}")
    print("[PASS] V45 built-in settings first; Local VPN/Refresh unchanged")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v45_builtin_settings.py <pinned-sidestore-root>")
    main(Path(sys.argv[1]))
