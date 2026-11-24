#!/usr/bin/env python3
"""Verify cumulative release identity and compiled feature evidence in one IPA.

This is an artifact integrity gate, not a signed-device acceptance test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import zipfile

PREFIX = "Payload/LiveContainer.app/"
REQUIRED_MARKERS = {
    "Frameworks/LiveContainerShared.framework/LiveContainerShared": (
        b"classic_bootstrap_armed",
        b"ScarletFullscreenGuestTabInstaller",
    ),
    "Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI": (
        b"_applicationIconImageForBundleIdentifier:format:scale:",
        b"automatic_deferred_interactive_settings",
        b"automatic_deferred_native_busy",
        b"classic_geometry_on_exit",
        b"classic_handoff_imported",
    ),
    "Frameworks/SideStoreSupport.framework/SideStoreSupport": (
        b"selected_account_app_mismatch",
        b"ready_inventory_unavailable",
    ),
    "Frameworks/SideStoreApp.framework/SideStore": (
        b"selected_account_app_mismatch",
        b"ready_inventory_unavailable",
        b"scarlet.certificate.team_operation_in_progress",
    ),
}

def require(condition, message):
    if not condition:
        raise ValueError(message)

def verify(ipa: Path, version: str, source_commit: str) -> dict:
    require(re.fullmatch(r"[0-9a-f]{40}", source_commit), "Invalid source SHA")
    with zipfile.ZipFile(ipa) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), "Duplicate archive members")
        bad = z.testzip()
        require(bad is None, f"Corrupt archive member: {bad}")
        info = plistlib.loads(z.read(PREFIX + "Info.plist"))
        require(info.get("CFBundleIdentifier") == "com.kdt.livecontainer.P8EZT3U5N4",
                "Unexpected host bundle identity")
        require(info.get("CFBundleShortVersionString") == "3.8.11",
                "Unexpected host marketing version")
        require(info.get("CFBundleVersion") == version, "Wrong host build version")
        require(info.get("CFBundleExecutable") == "LiveContainer", "Unexpected host executable")
        for relative, markers in REQUIRED_MARKERS.items():
            require(PREFIX + relative in names, f"Missing component: {relative}")
            binary = z.read(PREFIX + relative)
            for marker in markers:
                require(marker in binary, f"Missing compiled marker in {relative}: {marker.decode()}")
            if relative == "Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI":
                stamp = ("scarlet-source-commit:" + source_commit).encode("ascii")
                require(stamp in binary, "Host source stamp mismatch")
        if tuple(map(int, version.split("."))) >= (3, 8, 133):
            action_name = "ScarletSelfUpdateIntent"
            meta_path = "Metadata.appintents/extract.actionsdata"
            host_path = "Frameworks/LiveContainerSwiftUI.framework/"
            meta = json.loads(z.read(PREFIX + meta_path))
            generated = json.loads(z.read(PREFIX + host_path + meta_path))
            actions = meta.get("actions", {})
            action = generated.get("actions", {}).get(action_name)
            require(isinstance(action, dict) and actions.get(action_name) == action and
                    action.get("fullyQualifiedTypeName") == "LiveContainerSwiftUI.ScarletSelfUpdateIntent",
                    "Compiled shortcut metadata missing or altered")
            require(all(k in actions for k in ("RefreshAllIntent", "RefreshAllAppsWidgetIntent", "InstallIPAIntent")),
                    "Existing SideStore shortcut metadata lost")
            for binary_path, markers in (
                (host_path + "LiveContainerSwiftUI", (b"ScarletSelfUpdateIntent", b"shortcut_update_installed_build_verified")),
                ("Frameworks/SideStoreApp.framework/SideStore", (b"self_update_identity_unverified", b"Scarlet self-update signed identity or version mismatch")),
            ):
                binary = z.read(PREFIX + binary_path)
                require(all(m in binary for m in markers), f"Shortcut native code missing: {binary_path}")
        if tuple(map(int, version.split("."))) >= (3, 8, 134):
            binary = z.read(PREFIX + "Frameworks/SideStoreApp.framework/SideStore")
            require(all(marker in binary for marker in (
                b"self_update_archive_unverified",
                b"Scarlet self-update archive digest mismatch",
                b"Scarlet self-update source topology mismatch",
                b"Scarlet self-update provisioning Team mismatch")),
                "R134 worker integrity or preportal pin missing")
    with ipa.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return {"schema": 1, "sourceCommit": source_commit, "version": version,
            "sha256": digest, "bundleIdentifier": info["CFBundleIdentifier"],
            "size": ipa.stat().st_size, "compiledComponents": list(REQUIRED_MARKERS),
            "deviceVerified": False, "signed": False}

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ipa", type=Path, required=True)
    p.add_argument("--version", required=True)
    p.add_argument("--source-commit", required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    result = verify(args.ipa, args.version, args.source_commit)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print("[PASS] One cumulative IPA, correct source stamp, version, component markers and SHA-256")

if __name__ == "__main__":
    main()
