#!/usr/bin/env python3
"""V118: advance an authorized Apple login to its real 2FA challenge.

GrandSlam init failed with Apple -80045 before any challenge on V201.
Use the upstream SideInstaller 1.6.1 current-Mac *request* identity with a
profile-consistent User-Agent for Mac Anisette. Do not synthesize a challenge,
auto-submit codes, reset ADI, erase accounts, rotate servers, or touch signing.
Only Apple can return a 2FA-required state; existing trusted-device/SMS UI
remains the single source of truth.
"""
import argparse
from pathlib import Path

MARK = "SCARLET_V118_2FA_GATEWAY"
REL = Path("Sources/DeveloperPortal/Authentication.swift")
OLD_MAC = '''            // Preserve modern Mac profiles; normalize macOS 10.12 and earlier.
            if nrgGSAIsLegacyMac(original) {
                return "<MacBookPro18,3> <macOS;26.6;25F84> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
            }
            return original'''
NEW_MAC = '''            // SCARLET_V118_2FA_GATEWAY: SideInstaller 1.6.1 current-Mac
            // GrandSlam request profile, not a mutation of Anisette or ADI.
            // Do not fake an Apple 2FA challenge if init is still rejected.
            return "<Mac15,7> <macOS;27.0;26A5378j> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"'''
OLD_UA = '''        if nrgGSAIsLegacyMac(original) {
            return "AuthKit/1 (Macintosh; OS X 26.6) (com.apple.akd/1.0)"
        }
        if nrgGrandSlamUsesWindowsCompatibility(original) {
            return "akd/1.0 CFNetwork/808.1.4"
        }
        return fallback'''
NEW_UA = '''        // Use an akd UA for the normalized Mac and Windows AuthKit paths.
        // Keep fallback for other provider families, without rewriting ADI.
        if nrgGrandSlamClientInfo(original).contains("<macOS;")
            || nrgGrandSlamUsesWindowsCompatibility(original) {
            return "akd/1.0 CFNetwork/808.1.4"
        }
        return fallback'''
OLD_ACCEPT = '''            "Accept": "text/x-xml-plist",
            "User-Agent": nrgGrandSlamUserAgent(anisetteData.clientInfo, fallback: h.grandSlam.userAgent),'''
NEW_ACCEPT = '''            "Accept": "text/x-xml-plist",
            "Connection": "close",
            "User-Agent": nrgGrandSlamUserAgent(anisetteData.clientInfo, fallback: h.grandSlam.userAgent),'''
OLD_2FA = '''            "Content-Type": "application/x-plist",
            "User-Agent": nrgGrandSlamUserAgent(a.clientInfo, fallback: h.developerServices.userAgent),'''
NEW_2FA = '''            "Content-Type": "application/x-plist",
            "Connection": "close",
            "User-Agent": nrgGrandSlamUserAgent(a.clientInfo, fallback: h.developerServices.userAgent),'''

def once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"V118 {label}: expected exactly one match, got {count}")
    return source.replace(old, new, 1)

def audit(source: str) -> None:
    for required in ("SCARLET_V116_SIDEINSTALLER_PARITY", MARK, NEW_MAC,
                     NEW_UA, NEW_ACCEPT, NEW_2FA,
                     '"X-MMe-Client-Info": nrgGrandSlamClientInfo(anisetteData.clientInfo)',
                     '"X-MMe-Client-Info": nrgGrandSlamClientInfo(a.clientInfo)',
                     "NRG_GSA_RECOVERY_V1"):
        if required not in source:
            raise ValueError("V118 missing pinned authentication invariant")
    if source.count(MARK) != 1:
        raise ValueError("V118 unexpected marker count")
    for obsolete in (OLD_MAC, OLD_UA, OLD_ACCEPT, OLD_2FA):
        if obsolete in source:
            raise ValueError("V118 partial overlay")
    if 'AuthManager.shared.signOut()' in source:
        raise ValueError("V118 destructive signout unexpected")

def transform(source: str) -> str:
    if MARK in source:
        audit(source)
        return source
    for needed in ("SCARLET_V116_SIDEINSTALLER_PARITY", "SCARLET_V115_GSA_PROFILE_COHERENCE",
                   "NRG_GSA_CLIENT_IDENTITY_V3"):
        if needed not in source:
            raise ValueError(f"V118 prerequisite absent: {needed}")
    result = once(source, OLD_MAC, NEW_MAC, "modern Mac request identity")
    result = once(result, OLD_UA, NEW_UA, "GSA/2FA User-Agent policy")
    result = once(result, OLD_ACCEPT, NEW_ACCEPT, "GSA connection policy")
    result = once(result, OLD_2FA, NEW_2FA, "2FA connection policy")
    audit(result)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sidesign_root", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    target = args.sidesign_root / REL
    if not target.is_file() or target.is_symlink():
        parser.error("Pinned SideSign auth source unavailable")
    original = target.read_text(encoding="utf-8")
    modified = transform(original)
    if args.check:
        if MARK not in original or modified != original:
            parser.error("V118 overlay missing")
        print("SCARLET_V118_2FA_GATEWAY_CHECK_PASS")
    elif original != modified:
        target.write_text(modified, encoding="utf-8")
        print("SCARLET_V118_2FA_GATEWAY_APPLIED")
    else:
        print("SCARLET_V118_2FA_GATEWAY_ALREADY_APPLIED")

if __name__ == "__main__":
    main()
