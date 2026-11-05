#!/usr/bin/env python3
"""Inspect V189/V190 *published* signed IPA provisioning without disclosing device IDs.

A GitHub Release + SHA256 proves file integrity, not iOS OTA installability.
This tool is strictly read-only: it never alters an IPA, cert, key or profile.
"""
import datetime as dt
import json
import plistlib
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def read_profile(profile: bytes) -> dict:
    with tempfile.TemporaryDirectory() as temp:
        p = Path(temp) / "profile.mobileprovision"
        out = Path(temp) / "profile.plist"
        p.write_bytes(profile)
        proc = subprocess.run(
            ["openssl", "cms", "-verify", "-inform", "DER", "-noverify",
             "-in", str(p), "-out", str(out)],
            capture_output=True, text=True, timeout=25,
        )
        if proc.returncode != 0:
            raise ValueError("embedded provisioning CMS invalid or cannot be decoded")
        return plistlib.loads(out.read_bytes())


def scan(path: Path) -> dict:
    targets = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        profiles = [n for n in names
                    if n.startswith("Payload/") and n.endswith("/embedded.mobileprovision")
                    and (".app/" in n or ".appex/" in n)]
        if not profiles:
            raise ValueError("No embedded provisioning profiles")
        for prof in profiles:
            root = prof.removesuffix("embedded.mobileprovision")
            info_path = root + "Info.plist"
            if info_path not in names:
                raise ValueError("Missing Info.plist for " + root)
            info = plistlib.loads(z.read(info_path))
            provision = read_profile(z.read(prof))
            ent = provision.get("Entitlements", {})
            distribution = provision.get("ProvisionsAllDevices") is True
            development = ent.get("get-task-allow") is True
            dev_list = provision.get("ProvisionedDevices", [])
            if development:
                kind = "development"
            elif distribution:
                kind = "enterprise"
            elif dev_list:
                kind = "ad_hoc_candidate"
            else:
                kind = "app_store_or_other"
            identifier = info.get("CFBundleIdentifier", "")
            allowed = ent.get("application-identifier", "")
            teams = provision.get("TeamIdentifier", [])
            expires = provision.get("ExpirationDate")
            if expires and expires.tzinfo is None:
                expires = expires.replace(tzinfo=dt.timezone.utc)
            entry = {
                "bundle": identifier,
                "build": info.get("CFBundleVersion"),
                "display_build": info.get("ScarletBuildLabel"),
                "profile_kind": kind,
                "application_identifier_matches": bool(teams) and
                    allowed == teams[0] + "." + identifier,
                "application_groups_present": bool(
                    ent.get("com.apple.security.application-groups")),
                "profile_expired": bool(expires and expires < dt.datetime.now(dt.timezone.utc)),
                "has_registered_devices": bool(dev_list),
                "is_host": root.count(".app/") == 1 and ".appex/" not in root,
            }
            targets.append(entry)
    host = [t for t in targets if t["is_host"]]
    if len(host) != 1:
        raise ValueError("Expected one main iOS host")
    if host[0]["bundle"] != "com.kdt.livecontainer.P8EZT3U5N4":
        raise ValueError("Unexpected host bundle identity")
    # Compatibility result is about provisioning only, not a claim about
    # an iPhone installation (nor an end-to-end codesign validation).
    return {
        "file": path.name,
        "host_build": host[0]["build"],
        "host_label": host[0]["display_build"],
        "targets": sorted(targets, key=lambda e:e["bundle"]),
        "profile_consistency": all(t["application_identifier_matches"]
                and not t["profile_expired"] for t in targets),
        "safari_ota_distribution_profile_all_targets":
            all(t["profile_kind"] in ("ad_hoc_candidate", "enterprise")
                for t in targets),
        "codesign_cryptographic_validation": "not_run_linux",
        "device_install_validation": "not_run",
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: python3 audit_signed_ipa_provisioning.py <IPA> [IPA ...]")
    reports = [scan(Path(p)) for p in sys.argv[1:]]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
