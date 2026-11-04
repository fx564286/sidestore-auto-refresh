#!/usr/bin/env python3
"""Fail-closed recovery for missing Scarlet Crystal historical signing entitlements.

This script NEVER signs, installs, deletes/revokes certificates, changes App IDs,
or strips unsupported entitlements. It recovers the *existing* host entitlements
only after checking that all four current profiles belong to the correct app
and the host profile authorizes the historical Keychain/App Group/memory grants.
"""
from __future__ import annotations
import argparse
import datetime as dt
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

TEAM = "P8EZT3U5N4"
MAIN = "com.kdt.livecontainer.P8EZT3U5N4"
BUNDLES = {MAIN, *(MAIN+"."+s for s in ("LiveProcess","ShareExtension","LaunchAppExtension"))}
GROUPS = "com.apple.security.application-groups"
KEYCHAINS = "keychain-access-groups"
MEMORY = "com.apple.developer.kernel.increased-memory-limit"

class Halt(RuntimeError):
    pass

def decode_plist(blob):
    if not 0 < len(blob) < 512*1024:
        raise Halt("empty/oversized entitlement or provisioning document")
    try:
        data=plistlib.loads(blob)
    except (TypeError, ValueError, plistlib.InvalidFileException):
        raise Halt("not a readable entitlement plist") from None
    if not isinstance(data, dict):
        raise Halt("not a plist dictionary")
    return data

def historical_host(ent):
    if ent.get("application-identifier") != TEAM+"."+MAIN:
        raise Halt("historic application-identifier mismatch")
    if ent.get("com.apple.developer.team-identifier") != TEAM:
        raise Halt("historic Team ID mismatch")
    for key in (KEYCHAINS, GROUPS):
        groups=ent.get(key)
        if not isinstance(groups,list) or not groups or not all(isinstance(g,str) and g for g in groups):
            raise Halt("historic entitlement missing: "+key)
        if len(groups)!=len(set(groups)):
            raise Halt("duplicate entitlement group")
    return ent

def grants(value, allowed):
    return any(value==x or (x.endswith("*") and value.startswith(x[:-1])) for x in allowed)

def authorized(old, profile):
    historical_host(old)
    for key in (KEYCHAINS,GROUPS):
        values=profile.get(key)
        if not isinstance(values,list) or not values:
            raise Halt("Apple profile does not grant "+key+"; capability/profile renewal required")
        if not all(grants(v, values) for v in old[key]):
            raise Halt("Apple profile does not authorize preserved "+key+"; cannot force sign")
    if old.get(MEMORY) is True and profile.get(MEMORY) is not True:
        raise Halt("Apple profile lacks existing increased-memory entitlement")

def cms_profile(path):
    if not path.is_file():
        raise Halt("provisioning profile missing")
    try:
        p=subprocess.run(["openssl","cms","-verify","-inform","DER","-noverify"],
                         input=path.read_bytes(),capture_output=True,timeout=15)
    except (OSError,subprocess.TimeoutExpired):
        raise Halt("unable to verify CMS profile") from None
    if p.returncode:
        raise Halt("Apple CMS profile verification failed")
    return decode_plist(p.stdout)

def profile_info(blob):
    team=blob.get("TeamIdentifier",[])
    if TEAM not in team:
        raise Halt("Apple profile belongs to another Team")
    end=blob.get("ExpirationDate")
    if not isinstance(end,dt.datetime):
        raise Halt("profile expiration missing")
    if end.tzinfo is None:
        end=end.replace(tzinfo=dt.timezone.utc)
    if end<=dt.datetime.now(dt.timezone.utc):
        raise Halt("profile expired")
    ent=blob.get("Entitlements")
    if not isinstance(ent,dict):
        raise Halt("profile entitlements missing")
    appid=ent.get("application-identifier") or ent.get("com.apple.application-identifier")
    if not isinstance(appid,str) or not appid.startswith(TEAM+"."):
        raise Halt("provisioning App ID mismatch")
    return appid.removeprefix(TEAM+"."),ent

def signed_archive_host(ipa):
    if not shutil.which("ldid"):
        raise Halt("ldid is required to inspect a signed IPA")
    try:
        with zipfile.ZipFile(ipa) as z:
            prefix="Payload/LiveContainer.app/"
            info=plistlib.loads(z.read(prefix+"Info.plist"))
            if info.get("CFBundleIdentifier")!=MAIN:
                raise Halt("archive contains another app")
            executable=info.get("CFBundleExecutable")
            if not isinstance(executable,str) or "/" in executable or not executable:
                raise Halt("invalid executable name")
            binary=z.read(prefix+executable)
    except (OSError,zipfile.BadZipFile,KeyError,ValueError):
        raise Halt("IPA archive structure invalid") from None
    if len(binary)>200*1024*1024:
        raise Halt("invalid Mach-O size")
    with tempfile.TemporaryDirectory(prefix="scarlet-restore-") as tmp:
        path=Path(tmp)/"host"
        path.write_bytes(binary)
        run=subprocess.run(["ldid","-e",str(path)],capture_output=True,timeout=15)
        if run.returncode or not run.stdout:
            raise Halt("IPA has no extractable signed entitlements")
        return decode_plist(run.stdout)

def candidates(home):
    result=[]
    for root in (home/"다운로드",home/"Downloads",home/".local/state/scarlet-crystal-installer"):
        if not root.is_dir():
            continue
        for directory, dirs, names in os.walk(root,followlinks=False):
            dirs[:]=[x for x in dirs if x not in (".git","node_modules") and not x.startswith(".")]
            for name in names:
                low=name.lower()
                old_ent=("entitlement" in low and low.endswith((".xml",".plist")))
                old_ipa=("scarlet" in low and low.endswith(".ipa") and
                         "unsigned" not in low and "staged" not in low)
                if not (old_ent or old_ipa):
                    continue
                item=Path(directory)/name
                if item.is_file() and not item.is_symlink() and item.stat().st_size<300*1024*1024:
                    result.append(item)
                if len(result)>3000:
                    raise Halt("too many possible entitlement sources")
    return result

def recover(home,profiles,out,possible=None):
    if len(profiles)!=4:
        raise Halt("exactly four provisioning profiles required")
    rights={}
    for path in profiles:
        bid, grants=profile_info(cms_profile(path))
        if bid not in BUNDLES or bid in rights:
            raise Halt("four provisioning Bundle IDs incomplete/duplicated")
        rights[bid]=grants
    if set(rights)!=BUNDLES:
        raise Halt("four required provisioning Bundle IDs are not present")
    matches=[]; blocked=[]; checked=0
    for path in possible if possible is not None else candidates(home):
        checked+=1
        try:
            ent=(signed_archive_host(path) if path.suffix.lower()==".ipa"
                 else decode_plist(path.read_bytes()))
            historical_host(ent)
            authorized(ent,rights[MAIN])
            matches.append((len(ent[KEYCHAINS]),len(ent[GROUPS]),path.stat().st_mtime,ent))
        except (Halt,OSError,subprocess.TimeoutExpired) as e:
            blocked.append(str(e))
    if not matches:
        if any("com.apple.security.application-groups" in msg for msg in blocked):
            raise Halt("existing Apple profiles do not authorize historic App Group; restore capability, renew profiles, then retry")
        if any("increased-memory" in msg for msg in blocked):
            raise Halt("existing Apple profiles do not authorize historic memory entitlement")
        raise Halt(f"no eligible historic entitlement source found; checked {checked} candidate(s)")
    matches.sort(key=lambda x:x[:3],reverse=True)
    ent=matches[0][3]
    if out.exists() or out.is_symlink():
        raise Halt("refusing to overwrite an existing entitlement file")
    out.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(str(out),os.O_EXCL|os.O_CREAT|os.O_WRONLY,0o600)
    with os.fdopen(fd,"wb") as dest:
        dest.write(plistlib.dumps(ent,fmt=plistlib.FMT_XML))
    return len(ent[KEYCHAINS]),len(ent[GROUPS])

def main(argv):
    ap=argparse.ArgumentParser(description="Recover eligible Scarlet Crystal historic entitlement file without changing app or certificate")
    ap.add_argument("--profiles-dir",type=Path,required=True)
    ap.add_argument("--output",type=Path,default=Path.home()/".local/state/scarlet-crystal-installer/recovery/entitlements.xml")
    opts=ap.parse_args(argv)
    if os.geteuid()==0:
        raise Halt("do not run as root")
    profiles=sorted(opts.profiles_dir.expanduser().glob("*.mobileprovision"))
    keychains,groups=recover(Path.home(),profiles,opts.output.expanduser())
    print(f"[PASS] Historical host entitlements recovered, Keychain={keychains}, AppGroups={groups}")
    print("[OUTPUT]",opts.output.expanduser())
    print("[NEXT] Signer must verify signed entitlements for all 4 bundles before any upgrade")
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Halt as e:
        print("[STOP]",e,file=sys.stderr)
        raise SystemExit(2)
