#!/usr/bin/env python3
"""Offline-only NRG signing eligibility inventory.

Classifies existing iOS development profiles and PKCS12 certificate without
signing, installing, mutating developer account, or exposing key material.
An eligible bundle ID might already be installed: this audit NEVER authorizes
overwriting an app. Requires explicit on-device app inventory before install.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime,timezone
import hashlib
import importlib.util
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parent
BASE_SCRIPT=ROOT/"xtool_nrg_safe_signing_audit.py"
DEFAULT_TEAM="P8EZT3U5N4"
DEFAULT_UDID="00008160-000569490C600036"
ORIGINAL="com.kdt.livecontainer.P8EZT3U5N4"
PROBE="com.example.NRGLinuxProbe"


def read_module(path:Path):
    if not path.is_file():
        raise RuntimeError("Read-only base audit helper missing")
    spec=importlib.util.spec_from_file_location("nrg_readonly_sign_base",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_p12_private_key_present(p12:Path,password:Path):
    """Parse PKCS12 safely: OpenSSL -info -noout never exports key bytes."""
    if not p12.is_file() or not password.is_file():
        return "UNKNOWN"
    for legacy in [[],["-legacy"]]:
        try:
            p=subprocess.run(
                ["openssl","pkcs12","-info","-noout","-in",str(p12),
                 "-passin","file:"+str(password),*legacy],
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=18,check=False,
            )
        except (OSError,subprocess.TimeoutExpired):
            return "UNKNOWN"
        if p.returncode!=0:
            continue
        if re.search(rb"\b(?:shrouded keybag|key bag)\b",p.stderr,re.I):
            return "YES"
        return "NO"
    return "UNKNOWN"


def inventory_entry(profile:dict,team:str,udid:str,cert:bytes | None):
    ent=profile.get("Entitlements",{})
    if not isinstance(ent,dict):
        return None
    app=ent.get("application-identifier",ent.get("com.apple.application-identifier"))
    if not isinstance(app,str) or not app.startswith(team+"."):
        return None
    bundle=app[len(team)+1:]
    if not bundle or "*" in bundle:
        return None
    teams=profile.get("TeamIdentifier",[])
    if not isinstance(teams,list) or team not in teams:
        return None
    date=profile.get("ExpirationDate")
    if not isinstance(date,datetime):
        return None
    expiry=date.replace(tzinfo=timezone.utc) if date.tzinfo is None else date.astimezone(timezone.utc)
    if expiry <= datetime.now(timezone.utc):
        return None
    devices=profile.get("ProvisionedDevices",[])
    if not isinstance(devices,list) or udid not in devices:
        return None
    certs=profile.get("DeveloperCertificates",[])
    if not cert or not isinstance(certs,list):
        return None
    digest=hashlib.sha256(cert).digest()
    if not any(isinstance(c,bytes) and hashlib.sha256(c).digest()==digest for c in certs):
        return None
    return bundle


def summarize_bundles(bundles: list[str]):
    counts=Counter(bundles)
    protected={ORIGINAL,PROBE}
    candidates={}
    for bundle,n in counts.items():
        if bundle in protected:
            continue
        if bundle.startswith(ORIGINAL+"."):
            continue
        # Not a safety guarantee. Exclude obvious host SideStore aliases.
        if "sidestore" in bundle.lower() or "livecontainer" in bundle.lower():
            continue
        candidates[bundle]=n
    return counts,candidates


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--team",default=DEFAULT_TEAM)
    p.add_argument("--udid",default=DEFAULT_UDID)
    p.add_argument("--p12",type=Path)
    p.add_argument("--password-file",type=Path)
    p.add_argument("--candidates",action="store_true",help="print locally eligible non-NRG Bundle IDs for manual review (never install automatically)")
    args=p.parse_args()
    m=read_module(BASE_SCRIPT)
    p12=args.p12 or m.DEFAULT_P12
    pwd=args.password_file or p12.with_suffix(".password")
    cert,serial,valid=m.get_certificate(p12,pwd)
    print("=== PKCS12 INTEGRITY ===")
    print("P12_CERTIFICATE_VALID="+("YES" if cert and valid is True else "NO"))
    print("P12_PRIVATE_KEY_PRESENT="+get_p12_private_key_present(p12,pwd))
    good=[]
    count=0
    for _src,raw in m.candidate_profiles():
        profile=m.read_profile(raw)
        if not isinstance(profile,dict):
            continue
        count+=1
        bundle=inventory_entry(profile,args.team,args.udid,cert)
        if bundle:
            good.append(bundle)
    counts,candidates=summarize_bundles(good)
    print("=== VALID LOCAL PROFILES (NO SERVER MUTATION) ===")
    print("PROFILES_SCANNED="+str(count))
    print("FULLY_ELIGIBLE_PROFILES="+str(len(good)))
    print("UNIQUE_ELIGIBLE_BUNDLE_IDS="+str(len(counts)))
    print("ORIGINAL_NRG_PROFILES="+str(counts.get(ORIGINAL,0)))
    print("PROBE_PROFILES="+str(counts.get(PROBE,0)))
    print("OTHER_CANDIDATE_BUNDLE_IDS="+str(len(candidates)))
    if args.candidates:
        for bundle,n in sorted(candidates.items()):
            print(f"CANDIDATE_BUNDLE_ID={bundle} PROFILE_COPIES={n}")
        print("CANDIDATES_UNVERIFIED_ON_DEVICE=YES")
    if len(candidates)==0:
        print("NO_UNUSED_NATIVE_BUNDLE_ELIGIBILITY_PROVEN")
    print("SAFE_CONCLUSION=DO_NOT_AUTO_SIGN_OR_INSTALL")
    print("OFFLINE_AUDIT_ONLY_NO_PRIVATE_KEYS_EXPORTED")


if __name__=="__main__":
    main()
