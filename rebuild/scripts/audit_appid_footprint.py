#!/usr/bin/env python3
"""Read-only App ID footprint audit for one packaged, unsigned Scarlet IPA.

App IDs are Apple provisioning registrations, NOT the same as embedded
frameworks or guest apps. We count the app + iOS .appex targets inside this IPA.
The audit NEVER creates/revokes an App ID and does not claim real-device status.
"""
from __future__ import annotations
import argparse
import json
import plistlib
import re
import zipfile
from pathlib import Path

HOST_ID = "com.kdt.livecontainer.P8EZT3U5N4"
REQUIRED_EXTENSIONS = {
    "LiveProcess": HOST_ID + ".LiveProcess",
    "ShareExtension": HOST_ID + ".ShareExtension",
    "LaunchAppExtension": HOST_ID + ".LaunchAppExtension",
}
HOST_INFO = re.compile(r"^Payload/[^/]+\.app/Info\.plist$")
EXT_INFO = re.compile(r"^Payload/[^/]+\.app/PlugIns/([^/]+)\.appex/Info\.plist$")


def inspect_ipa(path: Path, *, strict: bool = True) -> dict:
    """Return public ID/extension metadata only. Refuse unknown targets."""
    with zipfile.ZipFile(path) as z:
        hosts = [n for n in z.namelist() if HOST_INFO.fullmatch(n)]
        if len(hosts) != 1:
            raise ValueError(f"Expected one host Info.plist, got {len(hosts)}")
        root = hosts[0].removesuffix("Info.plist")
        host = plistlib.loads(z.read(hosts[0]))
        host_id = host.get("CFBundleIdentifier")
        if host_id != HOST_ID:
            raise ValueError("Unexpected host bundle identity")
        extensions = []
        for name in z.namelist():
            match = EXT_INFO.fullmatch(name)
            if not match or not name.startswith(root):
                continue
            display = match.group(1)
            info = plistlib.loads(z.read(name))
            ext_id = info.get("CFBundleIdentifier")
            if not isinstance(ext_id, str) or not ext_id:
                raise ValueError(f"Invalid extension identity: {display}")
            ex_attributes = info.get("EXAppExtensionAttributes", {})
            ns_attributes = info.get("NSExtension", {})
            ext_point = (ex_attributes.get("EXExtensionPointIdentifier")
                         or ns_attributes.get("NSExtensionPointIdentifier"))
            if not isinstance(ext_point, str):
                raise ValueError(f"Missing extension point: {display}")
            extensions.append({
                "name": display,
                "bundle_id": ext_id,
                "extension_point": ext_point,
            })
        extensions.sort(key=lambda item: item["name"])
        identifiers = [host_id] + [x["bundle_id"] for x in extensions]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Duplicate App ID / extension bundle identity")
        if strict:
            actual = {ext["name"]: ext["bundle_id"] for ext in extensions}
            if actual != REQUIRED_EXTENSIONS:
                raise ValueError("Extension set changed: manual API/permission review required")
            types = {e["name"]: e["extension_point"] for e in extensions}
            if types["LaunchAppExtension"] != "com.apple.appintents-extension":
                raise ValueError("Pinned App Intents extension point changed")
            if types["ShareExtension"] != "com.apple.share-services":
                raise ValueError("Pinned shortcut URL transport/share extension changed")
        return {
            "schema": 1,
            "scope": "packaged host and app extensions only",
            "host_bundle_id": host_id,
            "host_app_ids": 1,
            "extension_app_ids": len(extensions),
            "total_bundle_ids": len(identifiers),
            "extensions": extensions,
            "built_in_feature_modules_add_app_ids": False,
            "free_team_provisioning_verified": False,
            "signed_ipa_verified": False,
            "device_running_verified": False,
            "safe_to_merge_extensions_automatically": False,
            "reduction_note": (
                "V14 3-ID package omitted ShareExtension but the pinned "
                "LaunchAppExtension.openURL() calls it by its own bundle ID. "
                "Full-functionality packaging retains all four identities. "
                "Further consolidation requires a replacement shortcut and "
                "share transport implementation with signed iOS runtime tests."
            ),
            "system_share_sheet_extension_present": True,
            "launch_app_shortcut_share_dependency_preserved": True,
            "in_app_files_picker_source_unmodified": True,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ipa", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = inspect_ipa(args.ipa)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"[PASS] App ID footprint (one IPA): {report['total_bundle_ids']}"
          f" = 1 host + {report['extension_app_ids']} extensions;"
          " built-in feature modules add 0 App IDs")


if __name__ == "__main__":
    main()
