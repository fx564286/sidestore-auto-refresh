#!/usr/bin/env python3
"""Read-only, no-secrets NRG signing audit V2.

Compares existing NRG and isolated Linux Probe entitlements against cached
profiles and the existing local P12 without generating certificates, app IDs,
profiles, Apple ID sessions, or performing installation.

Optional --remote only calls xtool's existing READ-ONLY 'ds teams list' and
'ds certificates list', reports *classified errors only*, never raw output.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess

HOME=Path.home()
SCRIPT=Path(__file__).with_name("xtool_nrg_safe_signing_audit.py")
TARGETS={
    "ORIGINAL_NRG":"com.kdt.livecontainer.P8EZT3U5N4",
    "ISOLATED_PROBE":"com.example.NRGLinuxProbe",
}
DEFAULT_UDID="00008160-000569490C600036"
DEFAULT_TEAM="P8EZT3U5N4"


def load_base():
    spec=importlib.util.spec_from_file_location("nrg_signing_v1",SCRIPT)
    if not SCRIPT.is_file():
        raise FileNotFoundError("Missing original read-only audit script")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def safe_certificate_status(output: str, returncode: int) -> str:
    """Never display opaque error body, IDs, URLs, account details or tokens."""
    if returncode==0:
        return "OK"
    s=output.lower()
    for name,pattern in [
        ("EXPIRED_SESSION",r"(session has expired|expired session|token expired|1100\b)"),
        ("UNAUTHORIZED",r"(http\s*401\b|status\s*401\b|unauthorized)"),
        ("FORBIDDEN",r"(http\s*403\b|status\s*403\b|forbidden|not authorized|permission denied)"),
        ("NOT_ENROLLED",r"(developer program membership|not enrolled|membership required)"),
        ("RATE_LIMIT",r"(http\s*429\b|rate limit)"),
        ("UNAVAILABLE",r"(http\s*50[0234]\b|status\s*50[0234]\b|temporarily unavailable)"),
        ("TIMEOUT",r"(optimeout|timed out|timeout)"),
        ("CONNECTIVITY",r"(dns|resolve host|connection refused|network unreachable|tls|ssl)"),
        ("INVALID_AUTH",r"(failed to authenticate|invalid token|invalid session)"),
        ("DECODING",r"(failed to decode|decodingerror|keynotfound|data corrupted)"),
    ]:
        if re.search(pattern,s):
            return name
    return "UNCLASSIFIED_FAILURE"


def remote_lookup(xtool: Path, team: str, cert_serial: str | None) -> None:
    if os.environ.get("NRG_XTOOL_SIDESTORE_AUTH")!="1" or not os.environ.get("NRG_XTOOL_COMPAT_STATE","").startswith("/"):
        print("REMOTE_CERT_STATUS=SKIPPED_NO_ISOLATED_AUTH")
        return
    if not xtool.is_file():
        print("REMOTE_CERT_STATUS=SKIPPED_XTOOL_MISSING")
        return

    for name, argv in [
        ("TEAMS",["ds","teams","list"]),
        ("CERT",["ds","certificates","list"]),
    ]:
        try:
            p=subprocess.run([str(xtool),*argv],stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                text=True,errors="replace",timeout=35,check=False)
            # The raw CLI output may contain account data; never echo any of it.
            status=safe_certificate_status(p.stdout+"\n"+p.stderr,p.returncode)
            if status=="OK" and name=="CERT":
                serials=set(x.upper().lstrip("0") for x in re.findall(
                    r"(?im)^\s*serial number:\s*([0-9A-F]+)\b",p.stdout))
                print("REMOTE_P12_CERT_MATCH="+("YES" if cert_serial and cert_serial in serials else "NO"))
            elif status=="OK" and name=="TEAMS":
                print("REMOTE_TEAM_MATCH="+("YES" if team in p.stdout else "NO"))
            print(f"REMOTE_{name}_STATUS={status}")
        except subprocess.TimeoutExpired:
            print(f"REMOTE_{name}_STATUS=TIMEOUT")
        except (OSError,ValueError):
            print(f"REMOTE_{name}_STATUS=PROCESS_ERROR")


def bits(p: dict, cert: bytes | None,team: str,bundle: str,udid: str):
    # Zero-trust: profile needs to match every condition simultaneously.
    ents=p.get("Entitlements",{})
    if not isinstance(ents,dict):
        ents={}
    ident=str(ents.get("application-identifier",
        ents.get("com.apple.application-identifier","")))
    team_ok=team in p.get("TeamIdentifier",[]) or ident.startswith(team+".")
    id_ok=ident in (team+"."+bundle,team+".*")
    expiry=p.get("ExpirationDate")
    import datetime
    utc=datetime.timezone.utc
    expiry_ok=isinstance(expiry,datetime.datetime) and (
        expiry.replace(tzinfo=utc) if expiry.tzinfo is None else expiry.astimezone(utc)
    )>datetime.datetime.now(utc)
    ids=p.get("ProvisionedDevices",[])
    device_ok=udid in ids if isinstance(ids,list) else False
    certificates=p.get("DeveloperCertificates",[])
    cert_ok=bool(cert) and isinstance(certificates,list) and any(
        isinstance(c,bytes) and hashlib.sha256(cert).digest()==hashlib.sha256(c).digest()
        for c in certificates)
    return team_ok,id_ok,expiry_ok,device_ok,cert_ok


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--team",default=DEFAULT_TEAM)
    ap.add_argument("--udid",default=DEFAULT_UDID)
    ap.add_argument("--remote",action="store_true",help="read-only Apple teams/cert registry queries")
    ap.add_argument("--p12",type=Path)
    ap.add_argument("--password-file",type=Path)
    ap.add_argument("--xtool",type=Path,default=HOME/"NRG-Tools/xtool-nrg-auth-v1/.build/release/xtool")
    args=ap.parse_args()
    base=load_base()
    p12=args.p12 or base.DEFAULT_P12
    password=args.password_file or p12.with_suffix(".password")
    cert,serial,valid=base.get_certificate(p12,password)
    print("=== EXISTING SIGNING IDENTITY ===")
    print("LOCAL_P12_PARSE="+("OK" if cert else "FAIL"))
    print("LOCAL_P12_TIME_VALID="+("YES" if valid else "NO" if valid is False else "UNKNOWN"))
    print("=== LOCAL PROFILE MATCH MATRIX ===")
    profiles=[]
    for _,raw in base.candidate_profiles():
        p=base.read_profile(raw)
        if isinstance(p,dict):
            profiles.append(p)
    print("PROFILE_COUNT="+str(len(profiles)))
    print("TEAM_PROFILE_COUNT="+str(sum(args.team in p.get("TeamIdentifier",[]) for p in profiles)))
    for name,bundle in TARGETS.items():
        matched=[bits(p,cert,args.team,bundle,args.udid) for p in profiles]
        checks=("TEAM","APP_ID","UNEXPIRED","DEVICE","P12_CERT")
        for i,field in enumerate(checks):
            print(f"{name}_{field}_COUNT="+str(sum(item[i] for item in matched)))
        print(f"{name}_FULLY_MATCHING_COUNT="+str(sum(all(item) for item in matched)))
    if args.remote:
        print("=== APPLE REGISTRY (READ ONLY) ===")
        remote_lookup(args.xtool,args.team,serial)
    print("READ_ONLY_NO_CERTIFICATE_OR_PROFILE_MUTATIONS")


if __name__=="__main__":
    main()
