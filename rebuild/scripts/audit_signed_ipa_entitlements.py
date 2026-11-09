#!/usr/bin/env python3
"""Audit a LOCALLY SIGNED Scarlet IPA after Apple signing (macOS only).

The GitHub release is unsigned. Selecting '12 permissions' in a third-party
signer does not prove Apple authorized them. A codesign signature and embedded
Apple-issued provisioning profile must agree for each signed bundle.

Does NOT sign, install, replace, decrypt, revoke or modify anything.
Reports only capability keys and booleans, not mobileprovision or secrets.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import zipfile


EXPECTED_GROUP = "group.com.SideStore.SideStore.P8EZT3U5N4"
EXPECTED_TEAM = "P8EZT3U5N4"
EXPECTED_HOSTS = {
    "com.kdt.livecontainer.P8EZT3U5N4",
    "com.kdt.livecontainer.P8EZT3U5N4.P8EZT3U5N4",
}
SELECTED_KEYS = {
    "Increased Memory Limit": "com.apple.developer.kernel.increased-memory-limit",
    "Extended Virtual Addressing": "com.apple.developer.kernel.extended-virtual-addressing",
    "Increased Debugging Memory Limit": "com.apple.developer.kernel.increased-debugging-memory-limit",
    "App Groups": "com.apple.security.application-groups",
    "Game Center": "com.apple.developer.game-center",
    "Inter-App Audio": "inter-app-audio",
}
# Screenshot items without a trustworthy one-to-one entitlement mapping are
# deliberately NOT declared enabled (e.g. In-App Purchase is not proved by
# a simple signing entitlement readback).

def run(*args: str) -> bytes:
    p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError(f"{args[0]} verification failed: exit {p.returncode}")
    return p.stdout


def plist(data: bytes) -> dict:
    # codesign may print diagnostics to stderr; plist is stdout.
    try:
        o = plistlib.loads(data)
    except Exception as e:
        raise RuntimeError("No readable signed entitlements / profile") from e
    if not isinstance(o, dict):
        raise RuntimeError("Unexpected entitlement object")
    return o


def matches_profile(value: object, allowed: object) -> bool:
    if isinstance(value, list):
        if not isinstance(allowed, list):
            return False
        # Apple's wildcards do NOT imply an arbitrary entitlement grant.
        return all(v in allowed for v in value)
    if isinstance(value, bool):
        return allowed is value
    if isinstance(value, str):
        return allowed == value or (
            isinstance(allowed, str) and allowed.endswith("*")
            and value.startswith(allowed[:-1]))
    return value == allowed


def inspect_bundle(path: Path) -> dict:
    info = plist((path / "Info.plist").read_bytes())
    bid = info.get("CFBundleIdentifier")
    if not isinstance(bid, str):
        raise RuntimeError("Bundle identifier missing")
    run("codesign", "--verify", "--strict", "--verbose=2", str(path))
    signed = plist(run("codesign", "-d", "--entitlements", "-", str(path)))
    mobile = path / "embedded.mobileprovision"
    if not mobile.is_file():
        raise RuntimeError("Apple-issued embedded.mobileprovision missing")
    profile = plist(run("security", "cms", "-D", "-i", str(mobile)))
    authorized = profile.get("Entitlements") or {}
    signed_id = signed.get("application-identifier")
    team = signed.get("com.apple.developer.team-identifier")
    profile_id = authorized.get("application-identifier")
    identity_ok = (
        team == EXPECTED_TEAM and
        signed_id == f"{EXPECTED_TEAM}.{bid}" and
        matches_profile(signed_id, profile_id)
    )
    unexpected = sorted(key for key, value in signed.items()
                        if key in authorized and
                        not matches_profile(value, authorized[key]))
    selected = {}
    for label, key in SELECTED_KEYS.items():
        value = signed.get(key)
        available = key in signed and key in authorized and matches_profile(value, authorized[key])
        # 'available' only means signed + profile match; it is not an OS
        # feature-use test or verification of private entitlements.
        selected[label] = "signed_and_profile_matched" if available else "not_verified"
    signed_groups = signed.get("com.apple.security.application-groups", [])
    authorized_groups = authorized.get("com.apple.security.application-groups", [])
    group_ok = (
        EXPECTED_GROUP in signed_groups and
        EXPECTED_GROUP in authorized_groups
        and matches_profile(signed_groups, authorized_groups)
    )
    return {
        "kind": "host" if path.suffix == ".app" else "extension",
        "bundleIdentityMatches": identity_ok,
        "profileTeamMatches": profile.get("TeamIdentifier", [None])[0] == EXPECTED_TEAM,
        "profileNotExpired": bool(profile.get("ExpirationDate") and
                                  profile["ExpirationDate"].timestamp() > __import__("time").time()),
        "appGroupGrantedAndSigned": group_ok,
        "profileMismatchKeys": unexpected,
        "selectedFeatureClaims": selected,
    }


def audit(ipa: Path) -> dict:
    with tempfile.TemporaryDirectory(prefix="scarlet-signed-audit-") as td:
        root = Path(td)
        # Preserve Mach-O executable permissions and Framework symlinks:
        # naive zipfile extraction corrupts the codesign seal.
        with zipfile.ZipFile(ipa) as z:
            for member in z.infolist():
                p = Path(member.filename)
                if p.is_absolute() or ".." in p.parts:
                    raise RuntimeError("Unsafe IPA path")
                if member.file_size > 200_000_000:
                    raise RuntimeError("Unexpectedly large IPA entry")
                if member.is_dir():
                    continue
                mode = (member.external_attr >> 16) & 0xffff
                target = root / p
                target.parent.mkdir(parents=True, exist_ok=True)
                if __import__("stat").S_ISLNK(mode):
                    link = z.read(member).decode("utf-8")
                    resolved = (target.parent / link).resolve()
                    if not resolved.is_relative_to(root):
                        raise RuntimeError("Unsafe IPA symlink")
                    os.symlink(link, target)
                else:
                    with z.open(member) as source, target.open("wb") as dest:
                        import shutil
                        shutil.copyfileobj(source, dest)
                    if mode:
                        target.chmod(mode & 0o777)
        apps = list((root / "Payload").glob("*.app"))
        if len(apps) != 1:
            raise RuntimeError("Expected exactly one signed host application")
        host = apps[0]
        info = plist((host / "Info.plist").read_bytes())
        if info.get("CFBundleIdentifier") not in EXPECTED_HOSTS:
            raise RuntimeError("Unexpected Scarlet host bundle identifier")
        bundles = [host] + sorted((host / "PlugIns").glob("*.appex"))
        results = [inspect_bundle(x) for x in bundles]
        return {
            "schema": 1,
            "signingMode": "installed_signature_artifact_readback_only",
            "bundleCount": len(results),
            "fourBundleProfileCheck": len(results) == 4,
            "hostIdentityValid": results[0]["bundleIdentityMatches"],
            "hostAppGroupValid": results[0]["appGroupGrantedAndSigned"],
            "allProfilesValid": all(x["profileTeamMatches"] and x["profileNotExpired"]
                                    for x in results),
            "allBundleSignaturesValid": all(x["bundleIdentityMatches"] for x in results),
            "bundles": results,
            "verifiedDeviceInstallation": False,
            "verifiedActualFeatureExecution": False,
        }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--signed-ipa", type=Path, required=True)
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    if sys.platform != "darwin":
        p.error("Run on macOS with Apple's codesign and security utilities")
    try:
        result = audit(args.signed_ipa)
    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as e:
        print("[BLOCKED] Signed entitlement audit:", e, file=sys.stderr)
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if result["fourBundleProfileCheck"] and result["hostIdentityValid"] and result["hostAppGroupValid"] and result["allProfilesValid"] and result["allBundleSignaturesValid"] else 3


if __name__ == "__main__":
    sys.exit(main())
