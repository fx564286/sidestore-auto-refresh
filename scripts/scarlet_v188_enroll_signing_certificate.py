#!/usr/bin/env python3
"""Scarlet Crystal V188: enroll ONE new Apple development identity without revocation.

Uses the tested local Apple/Anisette SRP workflow. The private key stays on the
user's CachyOS PC with mode 0600. Never uploads P12 or PEM private keys. The only
key-derived payload sent to Apple is a public-key certificate signing request.
Existing Team/App IDs/App Group and old app data are not modified.
"""
from __future__ import annotations

import datetime as dt
import getpass
import importlib.util
import os
from pathlib import Path
import re
import secrets
import ssl
import subprocess
import sys
import time
import uuid

HOME=Path.home()
WORK=HOME/".local/share/scarlet-crystal/v187"
SIGNING=HOME/".local/share/scarlet-crystal/signing"
IDENTITY=SIGNING/"identity-v188-enrolled"
CA=WORK/"tls/ca-bundle-with-apple.pem"
BASE=WORK/"apple-reconcile.py"
API=WORK/"vendor/sideinstaller-9ac886af5277dfc6bdecc6f9b21e53f8a45ad746.py"
TEAM="P8EZT3U5N4"
GROUP="group.com.SideStore.SideStore.P8EZT3U5N4"
APP="com.kdt.livecontainer.P8EZT3U5N4"
BUNDLES=[APP+s for s in ("",".LiveProcess",".ShareExtension",".LaunchAppExtension")]
KEY=IDENTITY/"private-key.pem"
CERT=IDENTITY/"certificate.pem"
ATTEMPT=IDENTITY/"csr-request-attempted.txt"
P12=IDENTITY/"identity.p12"
P12_PASS=IDENTITY/"identity-password.txt"

def fail(msg):
    raise RuntimeError("[STOP] "+msg)

def load(path,name):
    if not path.is_file():
        fail("REQUIRED_LOCAL_MODULE_MISSING: "+path.name)
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def openssl(args,data=None):
    p=subprocess.run(["openssl"]+list(args),input=data,capture_output=True)
    if p.returncode:
        fail("OPENSSL_FAILED: "+(" ".join(args[:3])))
    return p.stdout

def key_matches_cert(cert_der):
    public_from_key=openssl(["pkey","-in",str(KEY),"-pubout","-outform","DER"])
    pubpem=openssl(["x509","-inform","DER","-pubkey","-noout"],cert_der)
    public_from_cert=openssl(["pkey","-pubin","-outform","DER"],pubpem)
    return public_from_key==public_from_cert

def certificate_from_registry(api,session):
    certificates=session.call("listAllDevelopmentCerts",{"teamId":TEAM},
                              key="certificates")
    return [(item,bytes(item["certContent"])) for item in certificates
            if item.get("certContent")]

def find_issued_certificate(reconciler,certs):
    for item,der in certs:
        try:
            normalized=openssl(["x509","-inform","DER","-outform","DER"],der)
            if key_matches_cert(normalized):
                return item,normalized
        except RuntimeError:
            continue
    return None

def verify_existing_apple_state(session):
    teams=session.call("listTeams",key="teams",device_type="")
    team=next((x for x in teams if x.get("teamId")==TEAM),None)
    if team is None:
        fail("EXPECTED_TEAM_NOT_ACCESSIBLE")
    print("[PASS] EXISTING_TEAM",TEAM,"type="+str(team.get("type")),flush=True)
    listing=session.call("listAppIds",{"teamId":TEAM}).get("appIds",[])
    apps={x.get("identifier"):x for x in listing if x.get("identifier") in BUNDLES}
    if set(apps)!=set(BUNDLES):
        fail("EXPECTED_FOUR_EXISTING_APP_IDS_NOT_FOUND")
    if any(not apps[x].get("features",{}).get("APG3427HIY") for x in BUNDLES):
        fail("EXISTING_APP_GROUP_FEATURE_NOT_ENABLED_ON_ALL_IDS")
    groups=session.call("listApplicationGroups",{"teamId":TEAM},
                        key="applicationGroupList")
    if not any(x.get("identifier")==GROUP for x in groups):
        fail("EXISTING_APP_GROUP_NOT_FOUND")
    print("[PASS] FOUR_APP_IDS_AND_APP_GROUP",flush=True)
    return apps

def enroll_or_reuse_cert(session,reconciler):
    IDENTITY.mkdir(parents=True,exist_ok=True,mode=0o700)
    IDENTITY.chmod(0o700)
    certs=certificate_from_registry(None,session)
    print("[APPLE_CERTIFICATES_BEFORE]",len(certs),flush=True)
    if KEY.is_file():
        matched=find_issued_certificate(reconciler,certs)
        if matched:
            print("[PASS] RECOVERED_V188_KEY_ALREADY_REGISTERED",flush=True)
            return matched[1]
        if ATTEMPT.is_file():
            fail("CSR_PREVIOUSLY_SUBMITTED_BUT_CERT_NOT_LISTED; DO_NOT_CREATE_DUPLICATE")
        if CERT.is_file():
            fail("LOCAL_CERT_EXISTS_BUT_APPLE_DOES_NOT_REGISTER_IT")
    else:
        if ATTEMPT.exists() or CERT.exists():
            fail("INCONSISTENT_LOCAL_IDENTITY; DO_NOT_ISSUE_ANOTHER_CERT")
        if len(certs)>=2:
            fail("APPLE_CERTIFICATE_SLOT_UNCONFIRMED; NO_REVOCATION_ATTEMPTED")
        print("[CERTIFICATE] Generating one new private key locally",flush=True)
        openssl(["genpkey","-algorithm","RSA","-pkeyopt","rsa_keygen_bits:2048",
                 "-out",str(KEY)])
        KEY.chmod(0o600)
    if not KEY.is_file():
        fail("LOCAL_PRIVATE_KEY_NOT_AVAILABLE")
    if len(certs)>=2:
        fail("APPLE_CERTIFICATE_SLOT_UNCONFIRMED; NO_REVOCATION_ATTEMPTED")
    csr=openssl(["req","-new","-key",str(KEY),"-sha256",
                 "-subj","/C=US/O=Scarlet Crystal/CN=Scarlet Crystal V188"])
    machine_id=str(uuid.uuid4()).upper()
    # Persist a one-shot guard BEFORE network submission to avoid accidentally
    # burning multiple cert slots after a timeout or interrupted session.
    ATTEMPT.write_text("attempt="+dt.datetime.now(dt.timezone.utc).isoformat()+
                       "\nmachine_id="+machine_id+"\n",encoding="utf-8")
    ATTEMPT.chmod(0o600)
    print("[APPLE_CERT_ISSUE] Submitting single public-key CSR; no revoke",flush=True)
    reply=session.call("submitDevelopmentCSR",{
        "teamId":TEAM,
        "csrContent":csr.decode("ascii"),
        "machineName":"Scarlet Crystal V188 Existing App Renewal",
        "machineId":machine_id,
    },key="certRequest")
    if not reply.get("certRequestId"):
        fail("APPLE_DID_NOT_RETURN_CERTIFICATE_REQUEST_ID")
    for _ in range(7):
        found=find_issued_certificate(reconciler,certificate_from_registry(None,session))
        if found:
            print("[PASS] NEW_APPLE_CERTIFICATE_REGISTERED_AND_PRIVATE_KEY_MATCHED",flush=True)
            return found[1]
        time.sleep(2)
    fail("APPLE_ISSUED_CERT_NOT_YET_RETURNED; NEXT_RUN_REUSES_KEY_WITHOUT_RESUBMIT")

def write_identity(reconciler,cert_der):
    normalized=openssl(["x509","-inform","DER","-outform","DER"],cert_der)
    if not key_matches_cert(normalized):
        fail("APPLE_CERT_PRIVATE_KEY_MISMATCH")
    if CERT.is_file():
        old=openssl(["x509","-in",str(CERT),"-outform","DER"])
        if old!=normalized:
            fail("CERTIFICATE_CHANGED_UNEXPECTEDLY")
    else:
        CERT.write_bytes(openssl(["x509","-inform","DER","-outform","PEM"],normalized))
        CERT.chmod(0o600)
    if not P12_PASS.exists():
        P12_PASS.write_text(secrets.token_urlsafe(40),encoding="ascii")
        P12_PASS.chmod(0o600)
    if not P12.exists():
        openssl(["pkcs12","-export","-inkey",str(KEY),"-in",str(CERT),
                 "-out",str(P12),"-passout","file:"+str(P12_PASS),
                 "-name","Scarlet Crystal V188"])
        P12.chmod(0o600)
    print("[PASS] LOCAL_APPLE_IDENTITY_P12_STORED",flush=True)
    return reconciler.sha(normalized)

def issue_profiles(session, apps, cert_sha, reconciler):
    previous=reconciler.RECOVERY/"profile-0.mobileprovision"
    if not previous.is_file():
        fail("PREVIOUS_DEVICE_REFERENCE_MISSING")
    original=set(reconciler.read_profile(previous.read_bytes()).get("ProvisionedDevices",[]))
    if not original:
        fail("ORIGINAL_DEVICE_REFERENCE_EMPTY")
    candidate=IDENTITY/("profiles-"+dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                         +"-"+secrets.token_hex(3))
    candidate.mkdir(parents=True,mode=0o700)
    ready=[]
    for bundle in BUNDLES:
        response=session.call("downloadTeamProvisioningProfile",{
            "teamId":TEAM,"appIdId":apps[bundle]["appIdId"],
        },key="provisioningProfile")
        raw=bytes(response["encodedProfile"])
        info=reconciler.read_profile(raw)
        ent=info.get("Entitlements",{})
        certs=set()
        for c in info.get("DeveloperCertificates",[]):
            try:
                certs.add(reconciler.sha(openssl(
                    ["x509","-inform","DER","-outform","DER"],bytes(c))))
            except RuntimeError:
                pass
        expected=TEAM+"."+bundle
        status={
            "bundle":ent.get("application-identifier")==expected,
            "group":GROUP in ent.get("com.apple.security.application-groups",[]),
            "cert":cert_sha in certs,
            "device":original.issubset(set(info.get("ProvisionedDevices",[]))),
            "expiry":reconciler.valid_date(info.get("ExpirationDate")),
            "development":ent.get("get-task-allow") is True,
        }
        name="Main" if bundle==APP else bundle.rsplit(".",1)[-1]
        dest=candidate/(name+".mobileprovision")
        dest.write_bytes(raw);dest.chmod(0o600)
        print(("[PASS]" if all(status.values()) else "[BLOCKED]")+" PROFILE_"+name+
              " "+" ".join(k+"="+("1" if v else "0") for k,v in status.items()),
              flush=True)
        ready.append(all(status.values()))
    print("[PROFILES_SAVED]",candidate,flush=True)
    if not all(ready):
        fail("APPLE_PROFILES_NOT_READY_FOR_SAME_KEY_AND_GROUP")
    print("[PASS] FOUR_PROFILES_AUTHORIZED_V188",flush=True)
    print("[SIGNING_IDENTITY]",P12,flush=True)
    print("[SIGNING_PASSWORD_FILE]",P12_PASS,flush=True)
    print("[NEXT] Sign V188 IPA preserving four bundle IDs and original entitlements; do not remove installed app",flush=True)

def main():
    os.umask(0o077)
    if not CA.is_file() or CA.stat().st_size<1000:
        fail("LOCAL_APPLE_CA_TRUST_BUNDLE_MISSING")
    os.environ["SSL_CERT_FILE"]=str(CA)
    ssl.create_default_context().load_verify_locations(cafile=str(CA))
    reconciler=load(BASE,"scarlet_apple_reconcile")
    api=load(API,"scarlet_apple_backend")
    # Authenticate before doing anything to Apple's certificate registry.
    email=input("Apple ID email (local): ").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+",email):
        fail("APPLE_ID_REQUIRED")
    password=getpass.getpass("Apple ID password (hidden, local): ")
    if not password:
        fail("PASSWORD_REQUIRED")
    state=HOME/".local/state/scarlet-v187-apple"
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    anisette,gs=api.connect_anisette(api.FALLBACK_ANISETTE,str(state/"anisette.json"))
    account=api.AppleAccount(email,gs,anisette)
    try:
        account.login(password,lambda prompt:re.sub(r"\D","",getpass.getpass(prompt+" (hidden): ")))
    finally:
        password=None
    token,adsid=account.app_token("xcode.auth")
    session=api.DeveloperSession(account,token,adsid)
    apps=verify_existing_apple_state(session)
    # A new issuance is avoided if the exact intended key is already registered.
    der=enroll_or_reuse_cert(session,reconciler)
    digest=write_identity(reconciler,der)
    issue_profiles(session,apps,digest,reconciler)

if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[STOP] CANCELLED; existing Apple certificate and local keys preserved",file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print("[STOP] V188_CERT_ENROLLMENT:",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(1)
