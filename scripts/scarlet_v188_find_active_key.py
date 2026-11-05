#!/usr/bin/env python3
"""Read-only: locate any private key matching the active Apple certificate in all 4 V188 profiles.
No network/Apple operations, deletions, key uploads, or credentials printed.
"""
import datetime as dt
import os
from pathlib import Path
import plistlib
import subprocess
import sys

H=Path.home()
BASE=H/".local/share/scarlet-crystal"
T="P8EZT3U5N4"
B="com.kdt.livecontainer.P8EZT3U5N4"
G="group.com.SideStore.SideStore.P8EZT3U5N4"
LABELS=[("Main",B),("LiveProcess",B+".LiveProcess"),("ShareExtension",B+".ShareExtension"),("LaunchAppExtension",B+".LaunchAppExtension")]

def run(cmd, data=None):
    try:
        p=subprocess.run(cmd,input=data,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=12)
        return p.stdout if p.returncode==0 else None
    except (OSError,subprocess.TimeoutExpired):
        return None

def certpub(der):
    pem=run(["openssl","x509","-inform","DER","-pubkey","-noout"],der)
    return run(["openssl","pkey","-pubin","-outform","DER"],pem) if pem else None

def profile(path):
    cms=run(["openssl","cms","-verify","-inform","DER","-in",str(path),"-noverify"])
    return plistlib.loads(cms) if cms else None

def candidates():
    roots=[BASE,H/".sideinstaller",H/".local/state/scarlet-crystal-installer",
           H/".local/share/Trash/files/.sideinstaller",H/"Downloads",H/"다운로드"]
    found=set()
    for root in roots:
        if not root.is_dir():
            continue
        for d,dirs,names in os.walk(root):
            depth=len(Path(d).relative_to(root).parts)
            dirs[:]=[x for x in dirs if x not in {"node_modules","__pycache__",".git","target","build"}]
            if depth>=6:
                dirs[:]=[]
            for name in names:
                low=name.lower()
                if low.endswith((".p12",".pfx",".key")) or (low.endswith(".pem") and "key" in low):
                    found.add(Path(d)/name)
            if len(found)>=1500:
                print("[WARN] FILE_SEARCH_LIMIT")
                return sorted(found)[:1500]
    return sorted(found)

def passwords():
    p=[BASE/"signing/existing-identity.password",
       BASE/"recovery-backup/NRG-existing-signing-identity-v16.password",
       BASE/"signing/identity-v188-enrolled/identity-password.txt"]
    return ["pass:"]+["file:"+str(x) for x in p if x.is_file()]

def match(path, pub, passes):
    if path.suffix.lower() in (".p12",".pfx"):
        for pwd in passes:
            raw=run(["openssl","pkcs12","-in",str(path),"-nocerts","-nodes","-passin",pwd])
            if raw and run(["openssl","pkey","-pubout","-outform","DER","-passin","pass:"],raw)==pub:
                return "P12"
    else:
        for pwd in passes:
            if run(["openssl","pkey","-in",str(path),"-pubout","-outform","DER","-passin",pwd])==pub:
                return "PEM"
    return None

def main():
    dirs=sorted((BASE/"v187").glob("apple-reconcile-*/Main.mobileprovision"),key=lambda x:x.stat().st_mtime,reverse=True)
    if not dirs:
        print("[STOP] APPLE_PROFILES_NOT_FOUND")
        return 2
    folder=dirs[0].parent
    print("[PROFILE_SET]",folder)
    shared=None
    for label,bundle in LABELS:
        p=folder/(label+".mobileprovision")
        if not p.is_file():
            print("[STOP] PROFILE_MISSING",label); return 3
        info=profile(p)
        if not info:
            print("[STOP] INVALID_CMS",label);return 3
        rights=info.get("Entitlements",{})
        expiry=info.get("ExpirationDate")
        if isinstance(expiry,dt.datetime) and expiry.tzinfo is None:
            expiry=expiry.replace(tzinfo=dt.timezone.utc)
        if not (rights.get("application-identifier")==T+"."+bundle and
                G in rights.get("com.apple.security.application-groups",[]) and
                expiry and expiry>dt.datetime.now(dt.timezone.utc) and info.get("ProvisionedDevices")):
            print("[STOP] PROFILE_RIGHTS_INVALID",label);return 3
        pubkeys=set(x for cert in info.get("DeveloperCertificates",[]) if (x:=certpub(bytes(cert))))
        shared=pubkeys if shared is None else shared & pubkeys
        print("[PASS] PROFILE_VALID",label)
    if not shared:
        print("[STOP] APPLE_CERT_NOT_SHARED_ACROSS_FOUR_PROFILES");return 4
    files=candidates()
    print("[CANDIDATE_KEY_FILES]",len(files))
    found=[]
    pw=passwords()
    for path in files:
        for pub in shared:
            fmt=match(path,pub,pw)
            if fmt:
                print("[PASS] ACTIVE_APPLE_PRIVATE_KEY_FOUND",fmt,path)
                found.append(path)
                break
    marker=BASE/"signing/identity-v188-enrolled/csr-request-attempted.txt"
    if marker.is_file():
        print("[INFO] PREVIOUS_CSR_REQUEST_MARKER_PRESENT")
    if found:
        print("[PASS] KEY_RECOVERY_POSSIBLE; VERIFY_BUNDLE_AND_SIGNING_ENTITLEMENTS")
        return 0
    print("[STOP] NO_ACTIVE_PRIVATE_KEY_FOUND_IN_SCANNED_PATHS")
    print("[NEXT] Recover existing key from original signer or consider approved controlled replacement")
    print("[SAFETY] NO_REVOKE_NO_APP_INSTALL_NO_ACCOUNT_MUTATION")
    return 5

if __name__=="__main__":
    sys.exit(main())
