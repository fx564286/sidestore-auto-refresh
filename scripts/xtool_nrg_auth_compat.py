#!/usr/bin/env python3
"""Opt-in, isolated SideInstaller/NRG-style authentication experiment for xtool 1.22.2.

Never signs, installs, revokes certificates, modifies bundle IDs, or reads credentials.
Changes only a separate xtool source checkout at exact tag 1.22.2 (65bf3cc).
The alternate Anisette v3 host receives provisioning/OTP requests, NOT Apple passwords.
Authentication compatibility with Apple is experimental and not guaranteed.
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

PIN = "65bf3cc5a1240fea53ac0748d29a01878222a6ce"
MARKER = "NRG_XTOOL_SIDESTORE_AUTH_V1"

PATCHES = {
    "Sources/XKit/GrandSlam/Anisette/DeviceInfo.swift": [
        (
            "public struct DeviceInfo: Codable, Sendable {\n",
            """public struct DeviceInfo: Codable, Sendable {
    // NRG_XTOOL_SIDESTORE_AUTH_V1: activate only with isolated absolute state path.
    static var nrgSideStoreAuth: Bool {
        let environment = ProcessInfo.processInfo.environment
        return environment["NRG_XTOOL_SIDESTORE_AUTH"] == "1"
            && (environment["NRG_XTOOL_COMPAT_STATE"]?.hasPrefix("/") ?? false)
    }
    static let nrgWindowsClientInfo =
        "<PC> <Windows;6.2(0,0);9200> <com.apple.AuthKit/1 (com.apple.iTunes/12.12.4.1)>"

"""
        ),
    ],
    "Sources/XKit/Utilities/DirectoryProvider.swift": [
        (
            """    static let liveValue = PersistentDirectoryProvider(
        directory: URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent(".config/xtool")
    )""",
            """    // NRG_XTOOL_SIDESTORE_AUTH_V1: never mix experiment tokens/ADI with stock xtool.
    static let liveValue = PersistentDirectoryProvider(
        directory: ProcessInfo.processInfo.environment["NRG_XTOOL_COMPAT_STATE"]
            .flatMap { $0.hasPrefix("/") ? URL(fileURLWithPath: $0, isDirectory: true) : nil }
            ?? URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(".config/xtool")
    )"""
        ),
    ],
    "Sources/XKit/GrandSlam/Anisette/ADIDataProvider.swift": [
        (
            """    static let liveValue: RawADIProvider = {
        #if canImport(XADI)
        return XADIProvider()
        #else
        return OmnisetteADIProvider()
        #endif
    }()""",
            """    static let liveValue: RawADIProvider = {
        // NRG_XTOOL_SIDESTORE_AUTH_V1: previous SideInstaller path, v3 Omnisette.
        // Provider changed ONLY for the opt-in isolated test; no old ADI migrated.
        if DeviceInfo.nrgSideStoreAuth {
            return OmnisetteADIProvider(url: URL(string: "https://ani.jkcoxson.com")!)
        }
        #if canImport(XADI)
        return XADIProvider()
        #else
        return OmnisetteADIProvider()
        #endif
    }()"""
        ),
    ],
    "Sources/XKit/GrandSlam/Lookup/GrandSlamLookupManager.swift": [
        (
            """        let (_, body) = try await httpClient.makeRequest(request)

        return try self.decoder.decode(Response.self, from: body).urls""",
            r"""        // NRG_XTOOL_SIDESTORE_AUTH_V1: use a Mac URL-bag identity to avoid
        // the reduced Android GSA endpoint list. Do not change ADI provisioning.
        if DeviceInfo.nrgSideStoreAuth {
            request.headerFields[.init(DeviceInfo.clientInfoKey)!] =
                "<\(deviceInfo.modelID)> <Mac OS X;10.14.6;18G103> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
        }

        let (_, body) = try await httpClient.makeRequest(request)

        return try self.decoder.decode(Response.self, from: body).urls"""
        ),
    ],
    "Sources/XKit/GrandSlam/GrandSlamClient.swift": [
        (
            """        request.configure(request: &httpRequest, deviceInfo: deviceInfo, anisetteData: anisetteData)

        // GrandSlam doesn't seem to like reused""",
            """        request.configure(request: &httpRequest, deviceInfo: deviceInfo, anisetteData: anisetteData)
        // NRG_XTOOL_SIDESTORE_AUTH_V1: same GrandSlam identity for SRP and 2FA.
        // Never alter Anisette machine IDs, routing info or OTP fields.
        if DeviceInfo.nrgSideStoreAuth {
            httpRequest.headerFields[.init(DeviceInfo.clientInfoKey)!] = DeviceInfo.nrgWindowsClientInfo
            httpRequest.headerFields[.userAgent] = "akd/1.0 CFNetwork/808.1.4"
            httpRequest.headerFields[.init(DeviceInfo.xcodeVersionKey)!] = "14.2 (14C18)"
            httpRequest.headerFields[.init("X-Apple-App-Info")!] = "com.apple.gs.xcode.auth"
        }

        // GrandSlam doesn't seem to like reused"""
        ),
    ],
    "Sources/XKit/GrandSlam/Requests/GrandSlamOperationRequest.swift": [
        (
            """        clientData.merge(deviceInfo.dictionary) { _, b in b }
        clientData.merge(anisetteData.dictionary) { _, b in b }

        var request: [String: Any]""",
            """        clientData.merge(deviceInfo.dictionary) { _, b in b }
        clientData.merge(anisetteData.dictionary) { _, b in b }
        // NRG_XTOOL_SIDESTORE_AUTH_V1: align the SRP cpd payload with its header.
        if DeviceInfo.nrgSideStoreAuth {
            clientData[DeviceInfo.clientInfoKey] = DeviceInfo.nrgWindowsClientInfo
        }

        var request: [String: Any]"""
        ),
    ],
}


def patched(before: str, edits: list[tuple[str, str]], path: str) -> str:
    value = before
    for old, new in edits:
        if value.count(new) == 1:
            continue
        if value.count(old) != 1:
            raise ValueError(f"{path}: expected one upstream anchor; refusing ambiguous patch")
        value = value.replace(old, new, 1)
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xtool_checkout", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.xtool_checkout.resolve()
    if not (root / ".git").exists():
        parser.error("Expected a standalone git xtool checkout")
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
    except subprocess.CalledProcessError:
        parser.error("Unable to verify xtool upstream commit")
    if sha != PIN:
        parser.error("Only unmodified upstream tag 1.22.2 is supported")
    results: dict[Path, tuple[str, str]] = {}
    for relative, edits in PATCHES.items():
        path = root / relative
        original = path.read_text(encoding="utf-8")
        changed = patched(original, edits, relative)
        if args.check and (changed != original or MARKER not in original):
            parser.error(f"{relative}: compatibility patch missing or incomplete")
        results[path] = (original, changed)
    if args.apply:
        for path, (original, changed) in results.items():
            if original != changed:
                path.write_text(changed, encoding="utf-8")
    for path, (before, after) in results.items():
        print(("CHECK_OK" if args.check else "PATCHED" if before != after else "ALREADY_PATCHED"), path.relative_to(root))
    print("NRG_XTOOL_AUTH_COMPAT_READY: source-only, no login or signing performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
