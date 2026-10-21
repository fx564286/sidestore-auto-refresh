#!/usr/bin/env python3
"""SideInstaller-parity GrandSlam init request for an isolated xtool 1.22.2.

V3 patches request *shape* only, not Anisette provisioning, saved tokens, or Apple
credentials. Exact pinned source and V1 prerequisite checks; idempotent.
Compare FrizzleM/SideInstaller isideload anisette/mod.rs::get_client_provided_data.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

PIN = "65bf3cc5a1240fea53ac0748d29a01878222a6ce"
MARKER = "NRG_XTOOL_SIDESTORE_CPD_V3"
V1 = "NRG_XTOOL_SIDESTORE_AUTH_V1"

OPS = Path("Sources/XKit/GrandSlam/Requests/GrandSlamOperationRequest.swift")
CLIENT = Path("Sources/XKit/GrandSlam/GrandSlamClient.swift")
LOOKUP = Path("Sources/XKit/GrandSlam/Lookup/GrandSlamLookupManager.swift")

PATCHES = {
    OPS: [(
        """        // NRG_XTOOL_SIDESTORE_AUTH_V1: align the SRP cpd payload with its header.
        if DeviceInfo.nrgSideStoreAuth {
            clientData[DeviceInfo.clientInfoKey] = DeviceInfo.nrgWindowsClientInfo
        }""",
        """        // NRG_XTOOL_SIDESTORE_CPD_V3: match successful SideInstaller cpd exactly.
        // Apple may reject extra Mac hardware/ADI properties or different plist types.
        // Keep only three anisette/device fields; other six are STRING values.
        if DeviceInfo.nrgSideStoreAuth {
            clientData = [
                "bootstrap": "true",
                "icscrec": "true",
                "pbe": "false",
                "prkgen": "true",
                "svct": "iCloud",
                "loc": "en_US"
            ]
            for key in [
                AnisetteData.deviceIDKey,
                AnisetteData.machineIDKey,
                AnisetteData.oneTimePasswordKey
            ] {
                if let value = anisetteData.dictionary[key], !value.isEmpty {
                    clientData[key] = value
                }
            }
        }"""
    )],
    CLIENT: [(
        """            httpRequest.headerFields[.init("X-Apple-App-Info")!] = "com.apple.gs.xcode.auth"
        }""",
        """            httpRequest.headerFields[.init("X-Apple-App-Info")!] = "com.apple.gs.xcode.auth"
            // NRG_XTOOL_SIDESTORE_CPD_V3: SideInstaller GSA header parity.
            httpRequest.headerFields[.accept] = "text/x-xml-plist"
            httpRequest.headerFields[.init("Connection")!] = "close"
        }"""
    )],
    LOOKUP: [(
        r"""        // NRG_XTOOL_SIDESTORE_AUTH_V1: use a Mac URL-bag identity to avoid
        // the reduced Android GSA endpoint list. Do not change ADI provisioning.
        if DeviceInfo.nrgSideStoreAuth {
            request.headerFields[.init(DeviceInfo.clientInfoKey)!] =
                "<\(deviceInfo.modelID)> <Mac OS X;10.14.6;18G103> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
        }""",
        """        // NRG_XTOOL_SIDESTORE_CPD_V3: Windows ADI host returns full URL bag.
        // Avoid a contradictory Mac identity and unrelated Mac hardware device ID.
        if DeviceInfo.nrgSideStoreAuth {
            request.headerFields[.init(DeviceInfo.clientInfoKey)!] = DeviceInfo.nrgWindowsClientInfo
            request.headerFields[.init(DeviceInfo.deviceIDKey)!] = nil
            request.headerFields[.userAgent] = "akd/1.0 CFNetwork/808.1.4"
            request.headerFields[.contentType] = "text/x-xml-plist"
            request.headerFields[.accept] = "text/x-xml-plist"
            request.headerFields[.init(DeviceInfo.xcodeVersionKey)!] = "14.2 (14C18)"
            request.headerFields[.init("X-Apple-App-Info")!] = "com.apple.gs.xcode.auth"
        }"""
    )],
}


def transform(source: str, original: str, replacement: str, label: str) -> str:
    if replacement in source:
        if source.count(replacement) != 1:
            raise ValueError(f"{label}: repeated V3 patch")
        return source
    if source.count(original) != 1:
        raise ValueError(f"{label}: V1 source anchor missing or drifted")
    if V1 not in source:
        raise ValueError(f"{label}: V1 opt-in source prerequisite absent")
    return source.replace(original, replacement, 1)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("xtool_checkout", type=Path)
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument("--apply", action="store_true")
    action.add_argument("--check", action="store_true")
    args = p.parse_args()
    root = args.xtool_checkout.resolve()
    if not (root / ".git").is_dir():
        p.error("Refusing non-git checkout")
    pinned = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if pinned != PIN:
        p.error("Only xtool tag 1.22.2 pinned source may be patched")
    outputs: dict[Path, tuple[str, str]] = {}
    for relative, edits in PATCHES.items():
        file = root / relative
        original = file.read_text(encoding="utf-8")
        patched = original
        for before, after in edits:
            patched = transform(patched, before, after, str(relative))
        if args.check and (original != patched or MARKER not in original):
            p.error(f"Missing or partial V3 patch: {relative}")
        outputs[file] = (original, patched)
    if args.apply:
        for file, (old, new) in outputs.items():
            if old != new:
                file.write_text(new, encoding="utf-8")
    for file, (old, new) in outputs.items():
        print(
            ("CHECK_OK" if args.check else "PATCHED" if old != new else "ALREADY_PATCHED"),
            file.relative_to(root)
        )
    print("NRG_XTOOL_SIDESTORE_CPD_V3_PASS: source-only, no credentials or installation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
