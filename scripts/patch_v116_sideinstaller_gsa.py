#!/usr/bin/env python3
"""Scarlet V116: align SideSign GrandSlam and 2FA headers with SideInstaller.

Applies after the pinned V115 GSA/2FA patches. No network requests, no token,
ADI, keychain, certificate, provisioning, or account mutation.
"""
import argparse
from pathlib import Path

MARKER = "SCARLET_V116_SIDEINSTALLER_PARITY"

LEGACY_MAC_HELPER = r'''    // SCARLET_V116_SIDEINSTALLER_PARITY: SideInstaller's macOS ADI profile
    // normalizer. Anisette/ADI state is never changed: only request headers.
    private func nrgGSAIsLegacyMac(_ original: String) -> Bool {
        let markers = ["<Mac OS X;", "<macOS;"]
        guard let marker = markers.first(where: { original.contains($0) }),
              let range = original.range(of: marker) else { return false }
        let suffix = original[range.upperBound...]
        guard let version = suffix.split(separator: ";", maxSplits: 1).first else { return false }
        let numbers = version.split(separator: ".")
        guard numbers.count >= 2,
              let major = Int(numbers[0]), let minor = Int(numbers[1]) else { return false }
        return major < 10 || (major == 10 && minor < 13)
    }
    private func nrgGrandSlamUserAgent(_ original: String, fallback: String) -> String {
        // V117: classify the effective GSA profile before choosing the
        // user agent. An unsupported legacy-Mac-shaped source can legitimately
        // fall back to Windows; do not pair its Windows Client-Info with Mac UA.
        if nrgGrandSlamUsesWindowsCompatibility(original) {
            return "akd/1.0 CFNetwork/808.1.4"
        }
        if nrgGSAIsLegacyMac(original) {
            return "AuthKit/1 (Macintosh; OS X 26.6) (com.apple.akd/1.0)"
        }
        return fallback
    }
'''
NEW_MAC_BLOCK = '''        if hasAuthKit && (original.contains("<Mac") || original.contains("<iMac"))
            && (original.contains("<macOS;") || original.contains("<Mac OS X;")) {
            // Preserve modern Mac profiles; normalize macOS 10.12 and earlier.
            if nrgGSAIsLegacyMac(original) {
                return "<MacBookPro18,3> <macOS;26.6;25F84> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
            }
            return original
        }
'''
OLD_MAC_BLOCK = '''        if hasAuthKit && (original.contains("<Mac") || original.contains("<iMac"))
            && (original.contains("<macOS;") || original.contains("<Mac OS X;")) {
            return original
        }
'''
OLD_GSA_UA = '            "User-Agent": nrgGrandSlamUsesWindowsCompatibility(anisetteData.clientInfo) ? "akd/1.0 CFNetwork/808.1.4" : h.grandSlam.userAgent,'
NEW_GSA_UA = '            "User-Agent": nrgGrandSlamUserAgent(anisetteData.clientInfo, fallback: h.grandSlam.userAgent),'
OLD_2FA_UA = '            "User-Agent": nrgGrandSlamUsesWindowsCompatibility(a.clientInfo) ? "akd/1.0 CFNetwork/808.1.4" : h.developerServices.userAgent,'
NEW_2FA_UA = '            "User-Agent": nrgGrandSlamUserAgent(a.clientInfo, fallback: h.developerServices.userAgent),'
OLD_2FA_XCODE = '            "X-Xcode-Version": nrgGrandSlamUsesWindowsCompatibility(a.clientInfo) ? "14.2 (14C18)" : context.xcodeVersion,'
NEW_2FA_XCODE = '            "X-Xcode-Version": "14.2 (14C18)",'
OLD_GSA_EXTRA = '''        // SCARLET_V115_GSA_PROFILE_COHERENCE: legacy extra headers for Windows only.
        if nrgGrandSlamUsesWindowsCompatibility(anisetteData.clientInfo) {
            request.setValue("14.2 (14C18)", forHTTPHeaderField: "X-Xcode-Version")
            request.setValue("com.apple.gs.xcode.auth", forHTTPHeaderField: "X-Apple-App-Info")
        }'''
NEW_GSA_EXTRA = '''        // SCARLET_V116_SIDEINSTALLER_PARITY: SideInstaller sends both headers
        // for Mac and Windows clients, not just Windows ADI.
        request.setValue("14.2 (14C18)", forHTTPHeaderField: "X-Xcode-Version")
        request.setValue("com.apple.gs.xcode.auth", forHTTPHeaderField: "X-Apple-App-Info")
        debugLog("[SCARLET_V116_GSA_PROFILE] legacy_mac_normalized=\\(nrgGSAIsLegacyMac(anisetteData.clientInfo))")'''
OLD_GSA_ACCEPT = '            "Accept": "*/*",\n' + OLD_GSA_UA
NEW_GSA_ACCEPT = '            "Accept": "text/x-xml-plist",\n' + NEW_GSA_UA

def one(text: str, old: str, new: str, name: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"V116 {name}: pinned source mismatch (matches={count})")
    return text.replace(old, new, 1)

def transform(source: str) -> str:
    if MARKER in source:
        if (source.count(MARKER) != 2
                or NEW_GSA_ACCEPT not in source
                or NEW_MAC_BLOCK not in source
                or NEW_2FA_UA not in source
                or NEW_2FA_XCODE not in source):
            raise ValueError("V116 incomplete or corrupted marker")
        return source
    for prerequisite in ("NRG_GSA_RECOVERY_V1", "NRG_GSA_HTTP_STATUS_V2",
                         "SCARLET_V115_GSA_PROFILE_COHERENCE",
                         "NRG_GSA_CLIENT_IDENTITY_V3"):
        if prerequisite not in source:
            raise ValueError(f"V116 pinned prerequisite missing: {prerequisite}")
    result = one(source, OLD_MAC_BLOCK, NEW_MAC_BLOCK, "legacy mac")
    result = one(result,
        '    // SCARLET_V115_GSA_PROFILE_COHERENCE: choose auxiliary headers from',
        LEGACY_MAC_HELPER + '    // SCARLET_V115_GSA_PROFILE_COHERENCE: choose auxiliary headers from',
        "mac helper")
    result = one(result, OLD_GSA_ACCEPT, NEW_GSA_ACCEPT, "GSA accept/user agent")
    result = one(result, OLD_GSA_EXTRA, NEW_GSA_EXTRA, "GSA auxiliary headers")
    result = one(result, OLD_2FA_UA, NEW_2FA_UA, "2FA agent")
    result = one(result, OLD_2FA_XCODE, NEW_2FA_XCODE, "2FA xcode")
    # Keep both GSA and 2FA X-MMe-Client-Info routed through the same helper.
    assert result.count('"X-MMe-Client-Info": nrgGrandSlamClientInfo(') == 2
    for forbidden in ('AuthManager.shared.signOut()', 'adiPb =', 'resetAnisette',
                      'SecItemDelete('):
        if forbidden in LEGACY_MAC_HELPER + NEW_GSA_EXTRA:
            raise AssertionError("Unexpected identity mutation")
    return result

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("sidesign_root")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = Path(args.sidesign_root) / "Sources/DeveloperPortal/Authentication.swift"
    original = path.read_text(encoding="utf-8")
    updated = transform(original)
    if args.check:
        if original != updated or MARKER not in original:
            raise SystemExit("V116 check failed: not applied")
        print("[V116] SideInstaller GSA/2FA identity parity PASS")
    else:
        if original == updated:
            print("[V116] already applied")
        else:
            path.write_text(updated, encoding="utf-8")
            print("[V116] SideInstaller GSA/2FA request parity applied")

if __name__ == "__main__":
    main()
