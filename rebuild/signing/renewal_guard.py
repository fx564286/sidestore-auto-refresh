#!/usr/bin/env python3
"""Read-only free Personal Team provisioning expiry gate for Scarlet signed IPAs.

No certificate, Apple token, pairing file, UUID or App Group contents are printed.
Renewal is re-provision+re-sign+reinstall before expiry, not a permanent bypass.
"""
import argparse
import datetime as dt
import hashlib
import json
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

HOST = "com.kdt.livecontainer.P8EZT3U5N4"
REQUIRED = {
    HOST, HOST+".LiveProcess", HOST+".ShareExtension", HOST+".LaunchAppExtension"
}
UTC = dt.timezone.utc


def utc(value):
    if not isinstance(value, dt.datetime):
        raise ValueError("Invalid profile expiry")
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def decide(profiles, now, lead_hours=96):
    now = utc(now)
    seen = set()
    expiry = []
    flags = []
    for p in profiles:
        bundle = p["bundle"]
        if bundle in seen:
            raise ValueError("Duplicate profile for application component")
        seen.add(bundle)
        ent = p["entitlements"]
        teams = p["teams"]
        if not teams or ent.get("application-identifier") != teams[0] + "." + bundle:
            flags.append("bundle_entitlement_mismatch")
        if not ent.get("com.apple.security.application-groups"):
            flags.append("missing_app_group")
        if ent.get("get-task-allow") is not True:
            flags.append("not_free_development_profile")
        if not p["provisioned_devices"]:
            flags.append("no_device_registration")
        expiry.append(utc(p["expires"]))
    if seen != REQUIRED:
        flags.append("bundle_set_mismatch")
    if not expiry:
        raise ValueError("No provisioning profiles present")
    earliest = min(expiry)
    remaining = int((earliest-now).total_seconds()/3600)
    expired = earliest <= now
    due = earliest <= now + dt.timedelta(hours=lead_hours)
    state = ("blocked" if flags else "expired" if expired
             else "renewal_due" if due else "valid")
    return {
        "schema": 1,
        "state": state,
        "earliest_expiry_utc": earliest.isoformat(),
        "remaining_hours": remaining,
        "all_bundle_profiles_checked": len(profiles),
        "requirements_met": not flags,
        "blocking_categories": sorted(set(flags)),
        "install_eligibility": "requires_authorized_paired_device_or_working_on_device_installer",
        "automatic_ios_install_verified": False,
        "free_personal_team_seven_day_limit_removed": False
    }


def decode_cms(raw):
    with tempfile.TemporaryDirectory() as temp:
        src, dest=Path(temp)/"profile.cms", Path(temp)/"profile.plist"
        src.write_bytes(raw)
        proc=subprocess.run(["openssl","cms","-verify","-inform","DER",
                             "-noverify","-in",str(src),"-out",str(dest)],
                            capture_output=True,timeout=20)
        if proc.returncode != 0:
            raise ValueError("Invalid embedded profile CMS format or signature")
        return plistlib.loads(dest.read_bytes())


def inspect(path: Path):
    records=[]
    with ZipFile(path) as z:
        for member in z.namelist():
            if not (member.startswith("Payload/") and
                    member.endswith("/embedded.mobileprovision") and
                    (".app/" in member or ".appex/" in member)):
                continue
            info=member.rsplit("/",1)[0]+"/Info.plist"
            if info not in z.namelist():
                raise ValueError("Missing signed component Info.plist")
            bundle=plistlib.loads(z.read(info)).get("CFBundleIdentifier")
            if not isinstance(bundle,str):
                raise ValueError("Missing component Bundle ID")
            p=decode_cms(z.read(member))
            records.append({
                "bundle":bundle,
                "entitlements":p.get("Entitlements",{}),
                "teams":p.get("TeamIdentifier",[]),
                "expires":p.get("ExpirationDate"),
                "provisioned_devices":bool(p.get("ProvisionedDevices"))
            })
    return records


def main(argv=None):
    ap=argparse.ArgumentParser()
    ap.add_argument("--ipa",required=True,type=Path)
    ap.add_argument("--report",required=True,type=Path)
    ap.add_argument("--expected-sha256",default=None)
    ap.add_argument("--renew-before-hours",type=int,default=96)
    args=ap.parse_args(argv)
    if args.renew_before_hours<1 or args.renew_before_hours>168:
        raise ValueError("Unsafe renewal lead time")
    if args.expected_sha256:
        digest=hashlib.sha256(args.ipa.read_bytes()).hexdigest()
        if digest.lower()!=args.expected_sha256.lower():
            raise ValueError("Signed IPA SHA-256 mismatch")
    result=decide(inspect(args.ipa),dt.datetime.now(UTC),args.renew_before_hours)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+"\n")
    print("[PROFILE]",result["state"],"hours_remaining",result["remaining_hours"])
    print("[NOTICE] User-owned app, pairing state, Apple login/2FA and installation not altered")
    if result["state"] in ("blocked","expired"):
        sys.exit(2)

if __name__=="__main__":
    try:main()
    except (ValueError, OSError) as exc:
        print("[STOP] profile audit:",exc,file=sys.stderr)
        sys.exit(2)
