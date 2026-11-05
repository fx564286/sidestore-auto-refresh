#!/usr/bin/env python3
"""Scarlet Crystal V188: read-only Apple certificate/profile reconciliation.

Uses existing local SideInstaller Anisette v3/Apple SRP backend and separate trusted
Apple CA bundle. Requests live Apple Developer API reads and downloadable profiles
only. Does not change Apple App IDs, assign groups, register/revoke certificates,
delete apps, submit private keys, or install files. Profiles are stored as candidates,
never overwritten into the active app or signing directory.
"""
from __future__ import annotations
import datetime as dt
import getpass
import hashlib
import importlib.util
import os
from pathlib import Path
import plistlib
import re
import secrets
import ssl
import subprocess
import sys
import uuid

HOME = Path.home()
WORK = HOME / ".local/share/scarlet-crystal/v187"
SIGNING = HOME / ".local/share/scarlet-crystal/signing"
RECOVERY = HOME / ".local/share/scarlet-crystal/recovery-backup"
CA = WORK / "tls/ca-bundle-with-apple.pem"
OLD_BACKEND = WORK / "vendor/sideinstaller-9ac886af5277dfc6bdecc6f9b21e53f8a45ad746.py"
TEAM = "P8EZT3U5N4"
APP = "com.kdt.livecontainer.P8EZT3U5N4"
GROUP = "group.com.SideStore.SideStore.P8EZT3U5N4"
BUNDLES = [APP + x for x in ("", ".LiveProcess", ".ShareExtension", ".LaunchAppExtension")]

def abort(message: str):
    raise RuntimeError("[STOP] " + message)

def run(args, input_data=None):
    p = subprocess.run(args, input=input_data, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=False)
    if p.returncode:
        abort("CRYPTO_READ_FAILED")
    return p.stdout

def sha(der):
    return hashlib.sha256(der).hexdigest()

def normalize_der(cert_data):
    """OpenSSL cert public DER normalization, without emitting private material."""
    return run(["openssl","x509","-inform","DER","-outform","DER"], cert_data)

def cert_hash_from_pem(path):
    return sha(run(["openssl","x509","-in",str(path),"-outform","DER"]))

def p12_hash(p12,passfile):
    p = run(["openssl","pkcs12","-in",str(p12),"-clcerts","-nokeys",
             "-passin","file:"+str(passfile)])
    return sha(run(["openssl","x509","-outform","DER"],p))

def key_matches(key_path, cert_path):
    try:
        from_key=run(["openssl","pkey","-in",str(key_path),"-pubout","-outform","DER"])
        from_cert=run(["openssl","x509","-in",str(cert_path),"-pubkey","-noout"])
        pub=run(["openssl","pkey","-pubin","-outform","DER"],from_cert)
        return from_key == pub
    except RuntimeError:
        return False

def identities():
    out = {}
    p12 = SIGNING / "existing-identity.p12"
    pw = SIGNING / "existing-identity.password"
    if p12.is_file() and pw.is_file():
        out["existing-P12"]=p12_hash(p12,pw)
    cert=RECOVERY/"renewed-cert.pem"
    key=RECOVERY/"renewed-key.pem"
    if cert.is_file() and key.is_file() and key_matches(key,cert):
        out["renewed-PEM-keypair"]=cert_hash_from_pem(cert)
    if not out:
        abort("NO_VALID_LOCAL_KEYPAIR")
    return out

def read_profile(raw):
    decoded=run(["openssl","cms","-verify","-inform","DER","-noverify"],raw)
    return plistlib.loads(decoded)

def valid_date(t):
    if not isinstance(t,dt.datetime):
        return False
    if t.tzinfo is None:
        t=t.replace(tzinfo=dt.timezone.utc)
    return t > dt.datetime.now(dt.timezone.utc)

def cert_from_portal(item):
    c=item.get("certContent")
    if c is None:
        return None
    try:
        return sha(normalize_der(bytes(c)))
    except (RuntimeError,ValueError,TypeError):
        return None

def analyze_profile(p, expected_bundle, local, apple):
    e=p.get("Entitlements",{})
    hashes=[]
    for c in p.get("DeveloperCertificates",[]):
        try:
            hashes.append(sha(normalize_der(bytes(c))))
        except (RuntimeError,ValueError,TypeError):
            continue
    apple_matches=[name for name,h in local.items() if h in apple]
    profile_matches=[name for name,h in local.items() if h in hashes]
    return {
        "bundle_ok":e.get("application-identifier")==TEAM+"."+expected_bundle,
        "group_ok":GROUP in e.get("com.apple.security.application-groups",[]),
        "live":valid_date(p.get("ExpirationDate")),
        "device":bool(p.get("ProvisionedDevices")),
        "apple_matches":apple_matches,
        "profile_matches":profile_matches,
        "profile_cert_count":len(hashes),
        "created":p.get("CreationDate"),
        "expires":p.get("ExpirationDate"),
    }

def main():
    os.umask(0o077)
    if not CA.is_file() or CA.stat().st_size < 1000:
        abort("LOCAL_APPLE_CA_BUNDLE_MISSING")
    # The CA bundle is scoped to this process. Do not modify system trust.
    os.environ["SSL_CERT_FILE"]=str(CA)
    ssl.create_default_context().load_verify_locations(cafile=str(CA))
    if not OLD_BACKEND.is_file():
        abort("PINNED_SIDEINSTALLER_BACKEND_MISSING")
    local=identities()
    print("[PASS] LOCAL_IDENTITIES",",".join(local),flush=True)
    spec=importlib.util.spec_from_file_location("scarlet_signin_backend",OLD_BACKEND)
    api=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    email=input("Apple ID email (local): ").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+",email):
        abort("APPLE_ID_FORMAT")
    password=getpass.getpass("Apple ID password (hidden, local): ")
    if not password:
        abort("APPLE_PASSWORD_EMPTY")
    state=HOME/".local/state/scarlet-v187-apple"
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    anisette,gs=api.connect_anisette(api.FALLBACK_ANISETTE,str(state/"anisette.json"))
    acct=api.AppleAccount(email,gs,anisette)
    try:
        acct.login(password,lambda prompt:re.sub(r"\D","",getpass.getpass(prompt+" (hidden): ")))
    finally:
        password=None
    token,adsid=acct.app_token("xcode.auth")
    sess=api.DeveloperSession(acct,token,adsid)
    teams=sess.call("listTeams",key="teams",device_type="")
    team=next((t for t in teams if t.get("teamId")==TEAM),None)
    if team is None:
        abort("EXISTING_TEAM_NOT_ACCESSIBLE")
    print("[PASS] TEAM",TEAM,"TYPE",team.get("type","unknown"),flush=True)
    apps=sess.call("listAppIds",{"teamId":TEAM}).get("appIds",[])
    selected={a.get("identifier"):a for a in apps if a.get("identifier") in BUNDLES}
    if set(selected)!=set(BUNDLES):
        abort("ONE_OR_MORE_EXISTING_APP_IDS_MISSING")
    groups=sess.call("listApplicationGroups",{"teamId":TEAM},key="applicationGroupList")
    if not any(x.get("identifier")==GROUP for x in groups):
        abort("EXISTING_APP_GROUP_NOT_FOUND")
    print("[PASS] EXISTING_APP_IDS_AND_GROUP",flush=True)
    certs=sess.call("listAllDevelopmentCerts",{"teamId":TEAM},key="certificates")
    apple={h for x in certs if (h:=cert_from_portal(x))}
    matches=[name for name,h in local.items() if h in apple]
    print("[APPLE_CERTIFICATES] total=%d decoded=%d local_match=%s" %
          (len(certs),len(apple),",".join(matches) or "NONE"),flush=True)
    dest=WORK/("apple-reconcile-"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
               +"-"+secrets.token_hex(3))
    dest.mkdir(parents=True,exist_ok=False,mode=0o700)
    all_good=True
    for bundle in BUNDLES:
        a=selected[bundle]
        features=a.get("features",{})
        print("[APPLE_APP_ID] %s appgroup_feature=%s" %
              (bundle,str(features.get("APG3427HIY","absent"))),flush=True)
        obj=sess.call("downloadTeamProvisioningProfile",
                      {"teamId":TEAM,"appIdId":a["appIdId"]},
                      key="provisioningProfile")
        raw=bytes(obj["encodedProfile"])
        p=read_profile(raw)
        result=analyze_profile(p,bundle,local,apple)
        label="Main" if bundle==APP else bundle.rsplit(".",1)[-1]
        file=dest/(label+".mobileprovision")
        file.write_bytes(raw);file.chmod(0o600)
        ok=(result["bundle_ok"] and result["group_ok"] and result["live"] and
            result["device"] and bool(result["profile_matches"]) and
            bool(result["apple_matches"]))
        all_good=all_good and ok
        print(("[PASS]" if ok else "[BLOCKED]")+" APPLE_PROFILE "+
              "bundle="+bundle+" live=%d appid=%d group=%d device=%d certs=%d "
              "locally_authorized=%s apple_registry_match=%s" %
              (result["live"],result["bundle_ok"],result["group_ok"],
               result["device"],result["profile_cert_count"],
               ",".join(result["profile_matches"]) or "NONE",
               ",".join(result["apple_matches"]) or "NONE"),flush=True)
        print("[PROFILE_DATES] %s created=%s expires=%s" %
              (label,str(result["created"]),str(result["expires"])),flush=True)
    print("[CANDIDATE_PROFILES]",dest,flush=True)
    if all_good:
        print("[PASS] FOUR_APPLE_PROFILES_AUTHORIZE_SAME_RECOVERED_IDENTITY",flush=True)
        print("[NEXT] Verify actual IPA entitlements + existing Team ID before signing",flush=True)
        return 0
    if not matches:
        print("[ROOT_CAUSE] NEITHER_RECOVERED_CERT_IS_IN_ACTIVE_APPLE_CERTIFICATE_LIST",flush=True)
        print("[NEXT] New certificate issuance may be necessary; never auto-revoke existing certs",flush=True)
    else:
        print("[ROOT_CAUSE] APPLE_CERT_REGISTERED_BUT_ISSUED_PROFILES_NOT_IN_SYNC",flush=True)
        print("[NEXT] Inspect Apple App ID capability/profile issuance; do not patch CMS locally",flush=True)
    print("[STOP] V188_SIGNING_NOT_AUTHORIZED",flush=True)
    return 3

if __name__=="__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("[STOP] CANCELLED",file=sys.stderr)
        sys.exit(130)
    except Exception as ex:
        print("[STOP] RECONCILE_ERROR",type(ex).__name__,str(ex),file=sys.stderr)
        sys.exit(4)
