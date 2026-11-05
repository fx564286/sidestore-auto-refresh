#!/usr/bin/env python3
"""Read-only V188 audit: pair recovered signing identities with Apple-signed profiles.

No network, credential prompts, uploads, profile edits, or application installs.
Prints only public certificate matching and entitlement statuses; not private keys,
passwords, or device identifiers.
"""
import datetime as dt
import hashlib
import os
from pathlib import Path
import plistlib
import subprocess
import sys

TEAM="P8EZT3U5N4"
GROUP="group.com.SideStore.SideStore.P8EZT3U5N4"
APP="com.kdt.livecontainer.P8EZT3U5N4"
BUNDLES=[APP+s for s in ("", ".LiveProcess", ".ShareExtension", ".LaunchAppExtension")]
BASE=Path.home()/".local/share/scarlet-crystal"
BACKUP=BASE/"recovery-backup"
SIGN=BASE/"signing"
AUTO=Path.home()/".local/state/scarlet-crystal-installer/auto-renew"
V188=BASE/"v187"

def run(args,stdin=None):
    p=subprocess.run(args,input=stdin,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode:
        raise ValueError("OpenSSL verification failed")
    return p.stdout

def digest(der):
    return hashlib.sha256(der).hexdigest()

def cert_from_pem(pem):
    return run(["openssl","x509","-outform","DER"],pem)

def cert_from_p12(path,password_file):
    raw=run(["openssl","pkcs12","-in",str(path),"-clcerts","-nokeys",
             "-passin","file:"+str(password_file)])
    return cert_from_pem(raw)

def cert_from_file(path):
    return run(["openssl","x509","-in",str(path),"-outform","DER"])

def key_matches_cert(key_path,cert_der):
    try:
        pubkey=run(["openssl","pkey","-in",str(key_path),"-pubout","-outform","DER"])
        x509pub=run(["openssl","x509","-inform","DER","-pubkey","-noout"],cert_der)
        certpub=run(["openssl","pkey","-pubin","-outform","DER"],x509pub)
        return pubkey==certpub
    except Exception:
        return False

def get_identities():
    out={}
    p12=SIGN/"existing-identity.p12"
    password=SIGN/"existing-identity.password"
    if p12.is_file() and password.is_file():
        try:
            out["existing-P12"]=digest(cert_from_p12(p12,password))
        except Exception:
            print("[STOP] EXISTING_P12_UNREADABLE")
    cert=BACKUP/"renewed-cert.pem"
    key=BACKUP/"renewed-key.pem"
    if cert.is_file() and key.is_file():
        try:
            der=cert_from_file(cert)
            if key_matches_cert(key,der):
                out["renewed-PEM-keypair"]=digest(der)
            else:
                print("[WARN] RENEWED_CERT_KEY_MISMATCH_OR_ENCRYPTED")
        except Exception:
            print("[WARN] RENEWED_CERTIFICATE_UNREADABLE")
    return out

def decode(path):
    data=run(["openssl","cms","-verify","-inform","DER","-in",str(path),"-noverify"])
    return plistlib.loads(data)

def find_profiles():
    paths=set()
    for root in (BACKUP,AUTO,V188):
        if root.is_dir():
            paths.update(root.rglob("*.mobileprovision"))
    return sorted(paths, key=lambda p: str(p))

def main():
    identities=get_identities()
    print("[SIGNING_IDENTITIES]", ",".join(identities) if identities else "NONE")
    if not identities:
        return 2
    profiles=[]
    for path in find_profiles():
        try:
            p=decode(path)
        except Exception:
            continue
        ent=p.get("Entitlements",{})
        appid=ent.get("application-identifier","")
        if appid not in {TEAM+"."+b for b in BUNDLES}:
            continue
        expires=p.get("ExpirationDate")
        live=isinstance(expires,dt.datetime) and expires.replace(tzinfo=dt.timezone.utc)>dt.datetime.now(dt.timezone.utc)
        certs={digest(bytes(c)) for c in p.get("DeveloperCertificates",[])}
        groups=ent.get("com.apple.security.application-groups",[])
        matches=[name for name,h in identities.items() if h in certs]
        profiles.append(dict(bundle=appid[len(TEAM)+1:],date=expires,
                             live=live,group=GROUP in groups,
                             auth=matches,devices=bool(p.get("ProvisionedDevices"))))
    print("[PROFILES_FOUND]",len(profiles))
    all_good=True
    for bundle in BUNDLES:
        items=[x for x in profiles if x["bundle"]==bundle]
        good=[x for x in items if x["live"] and x["group"] and x["auth"] and x["devices"]]
        if good:
            chosen=max(good,key=lambda x:x["date"])
            print("[PASS] PROFILE_AUTHORIZED",bundle,"identity="+",".join(chosen["auth"]),"expires="+str(chosen["date"]))
        else:
            all_good=False
            summary=";".join("live=%d,group=%d,cert=%s,device=%d" %
                 (x["live"],x["group"],",".join(x["auth"]) or "NO_MATCH",x["devices"])
                 for x in sorted(items,key=lambda x:x["date"],reverse=True)[:2])
            print("[BLOCKED] PROFILE_NOT_READY",bundle,"candidates="+str(len(items)),summary)
    if all_good:
        print("[PASS] FOUR_PROFILES_AUTHORIZE_RECOVERED_KEYS")
        return 0
    print("[STOP] NO_SAFE_IN_PLACE_SIGNING_YET")
    print("[NEXT] Reissue Apple profiles with original App Group and an Apple-authorized cert whose private key exists locally.")
    return 3

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("[STOP] AUDIT_ERROR",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(4)
