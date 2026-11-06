#!/usr/bin/env python3
"""Read-only planning for Scarlet Crystal Personal Team 7-day refresh.

Apple's free Personal Team cannot issue Apple Distribution/Ad Hoc OTA profiles.
A valid paid entitlement is NOT inferred from a published GitHub IPA.
This module never creates/revokes a certificate or modifies a device.
A local signer may consume the emitted decision only after verifying
all four actual signed bundle profiles and installed app identity.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import sys

TEAM="P8EZT3U5N4"
HOST=f"com.kdt.livecontainer.{TEAM}"
BUNDLES=(HOST,HOST+".LiveProcess",HOST+".ShareExtension",HOST+".LaunchAppExtension")
THRESHOLD_HOURS=72

def parse_iso(value:str)->dt.datetime:
    if not isinstance(value,str):
        raise ValueError("Profile expiry must be ISO-8601")
    try:
        when=dt.datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as e:
        raise ValueError("Invalid profile expiry timestamp") from e
    if when.tzinfo is None:
        raise ValueError("Profile timestamp must specify timezone")
    return when.astimezone(dt.timezone.utc)

def evaluate(snapshot:dict, now:dt.datetime|None=None)->dict:
    now=(now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    if snapshot.get("team_id")!=TEAM or snapshot.get("bundle_id")!=HOST:
        raise ValueError("Unexpected app identity; do not change Team or Bundle ID")
    profiles=snapshot.get("profiles")
    if not isinstance(profiles,list) or len(profiles)!=4:
        raise ValueError("All four provisioning profiles must be inventoried")
    bundles=[x.get("bundle_id") for x in profiles if isinstance(x,dict)]
    if len(bundles)!=4 or set(bundles)!=set(BUNDLES):
        raise ValueError("Profile bundle IDs missing, duplicated or mismatched")
    checks=[]
    for p in profiles:
        name=p["bundle_id"]
        when=parse_iso(p.get("expires_at"))
        # Strict checks: no guessing a missing entitlement, identity, device
        # registration or Apple-issued profile validity. Do not revoke assets.
        for check in ("app_group_authorized","identity_matches","device_registered",
                      "cms_verified","certificate_authorized"):
            if p.get(check) is not True:
                checks.append({"bundle_id":name,"reason":check})
        if p.get("profile_kind")!="development":
            checks.append({"bundle_id":name,"reason":"unexpected_profile_kind"})
    closest=min(parse_iso(p["expires_at"]) for p in profiles)
    remaining=(closest-now).total_seconds()/3600
    expiring=remaining<=THRESHOLD_HOURS
    return {
        "schema":1,
        "account_kind":"free_personal_team",
        "team_id":TEAM,
        "bundle_id":HOST,
        "checked_at":now.isoformat(),
        "earliest_profile_expiry":closest.isoformat(),
        "hours_remaining":round(remaining,2),
        "threshold_hours":THRESHOLD_HOURS,
        "needs_refresh":expiring,
        "status":"BLOCKED" if checks else (
            "EXPIRED" if remaining<=0 else
            "REFRESH_DUE" if expiring else "VALID"),
        # "may attempt" is not "refreshed"; Apple authentication/2FA and
        # actual new-profile issuance are only known to the local signer.
        "local_refresh_preflight_ready":not bool(checks) and expiring,
        "installation_verified":False,
        "refresh_completed":False,
        "refused_conditions":checks,
        "next_actions":(
            ["Preserve existing certificates and app data",
             "Do not sign/install until missing identity and App Group checks pass"]
            if checks else
            ["Acquire fresh Apple-issued development provisioning for all four bundles",
             "Verify App Group and signed identity; re-sign, then upgrade installed app",
             "Confirm actual installed build on iPhone; never infer from 204/IPA upload"]
            if expiring else
            ["Keep signed assets and installed app unchanged; recheck expiry on schedule"]
        )
    }

def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--snapshot",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    args=p.parse_args(argv)
    snapshot=json.loads(args.snapshot.read_text(encoding="utf-8"))
    result=evaluate(snapshot)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"[RENEWAL] {result['status']} hours_remaining={result['hours_remaining']} "
          f"eligible_for_local_attempt={result['local_refresh_preflight_ready']}")
    if result["status"]=="BLOCKED":
        return 3
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as e:
        print(f"[STOP] REFRESH_PRECHECK {e}",file=sys.stderr)
        raise SystemExit(2)
