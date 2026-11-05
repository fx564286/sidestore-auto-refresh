#!/usr/bin/env python3
"""Replace exactly one verified Apple iOS DEVELOPMENT certificate for Scarlet V188.

The owner approved replacement of the single Apple certificate. This utility:
  * authenticates using the locally cached SideInstaller SRP+Anisette backend;
  * checks four existing App IDs, App Group, and Apple's signed profiles;
  * archives public certificate data before revoking the exact existing serial;
  * reuses the previously generated local RSA private key, never exports it;
  * submits one new CSR, NEVER automatically revokes multiple certificates;
  * downloads and audits four Apple signed profiles before reporting success.
It does NOT change app bundle IDs, delete apps or upload signing secrets.

WARNING: Revocation is IRREVERSIBLE; existing apps signed by that certificate
may fail until re-signed. No bypass of server TLS or entitlement checks.
"""
import datetime as dt
import getpass
import importlib.util
import json
import os
from pathlib import Path
import plistlib
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
KEY=IDENTITY/"private-key.pem"
CERT=IDENTITY/"certificate.pem"
P12=IDENTITY/"identity.p12"
PASSWORD_FILE=IDENTITY/"identity-password.txt"
STATE_FILE=IDENTITY/"replacement-state.json"
BACKUP=HOME/".local/share/scarlet-crystal/recovery-backup"
CA=WORK/"tls/ca-bundle-with-apple.pem"
BACKEND=WORK/"vendor/sideinstaller-9ac886af5277dfc6bdecc6f9b21e53f8a45ad746.py"
RECONCILER=WORK/"apple-reconcile.py"
TEAM="P8EZT3U5N4"
GROUP="group.com.SideStore.SideStore.P8EZT3U5N4"
APP="com.kdt.livecontainer.P8EZT3U5N4"
BUNDLES=[APP+x for x in ("",".LiveProcess",".ShareExtension",".LaunchAppExtension")]

def stop(reason):
    raise RuntimeError("[STOP] "+reason)

def run(args, data=None):
    p=subprocess.run(["openssl",*args],input=data,stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE,timeout=25)
    if p.returncode:
        stop("OPENSSL_OPERATION_FAILED")
    return p.stdout

def load_module(path,name):
    if not path.is_file():
        stop("DEPENDENCY_MISSING_"+path.name)
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def atomic_json(data):
    IDENTITY.mkdir(parents=True,exist_ok=True,mode=0o700)
    tmp=IDENTITY/(".replacement-state-"+secrets.token_hex(6))
    tmp.write_text(json.dumps(data,sort_keys=True,indent=2),encoding="utf8")
    tmp.chmod(0o600)
    tmp.replace(STATE_FILE)
    STATE_FILE.chmod(0o600)

def read_state():
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.is_file() else None

def cert_der(data):
    return run(["x509","-inform","DER","-outform","DER"],data)

def cert_public_key(der):
    pem=run(["x509","-inform","DER","-pubkey","-noout"],der)
    return run(["pkey","-pubin","-outform","DER"],pem)

def public_key_local():
    if not KEY.is_file():
        stop("PREVIOUSLY_CREATED_PRIVATE_KEY_MISSING; NO_NEW_KEY_CREATED")
    if KEY.is_symlink():
        stop("PRIVATE_KEY_SYMLINK_UNSAFE")
    return run(["pkey","-in",str(KEY),"-pubout","-outform","DER"])

def list_certs(session):
    return session.call("listAllDevelopmentCerts",{"teamId":TEAM},key="certificates")

def matching_cert(certs, public):
    for c in certs:
        raw=c.get("certContent")
        if not raw:
            continue
        try:
            der=cert_der(bytes(raw))
            if cert_public_key(der)==public:
                return c,der
        except (ValueError,RuntimeError):
            continue
    return None

def safe_four_app_ids(session):
    teams=session.call("listTeams",key="teams",device_type="")
    if not any(t.get("teamId")==TEAM for t in teams):
        stop("EXISTING_TEAM_NOT_ACCESSIBLE")
    apps=session.call("listAppIds",{"teamId":TEAM}).get("appIds",[])
    mapping={x.get("identifier"):x for x in apps if x.get("identifier") in BUNDLES}
    if set(mapping)!=set(BUNDLES):
        stop("FOUR_ORIGINAL_APP_IDS_NOT_FOUND")
    if any(not mapping[x].get("features",{}).get("APG3427HIY") for x in BUNDLES):
        stop("EXISTING_APP_GROUP_FEATURE_INCOMPLETE")
    groups=session.call("listApplicationGroups",{"teamId":TEAM},
                        key="applicationGroupList")
    if not any(g.get("identifier")==GROUP for g in groups):
        stop("ORIGINAL_APP_GROUP_MISSING")
    if not (BACKUP/"profile-0.mobileprovision").is_file():
        stop("ORIGINAL_DEVICE_REFERENCE_MISSING")
    print("[PASS] TEAM_APP_IDS_GROUP_DEVICE_REFERENCE",flush=True)
    return mapping

def original_devices(reconciler):
    p=reconciler.read_profile((BACKUP/"profile-0.mobileprovision").read_bytes())
    devices=set(p.get("ProvisionedDevices",[]))
    if not devices:
        stop("ORIGINAL_PROVISIONING_DEVICE_LIST_MISSING")
    return devices

def assert_old_cert_used_by_all_four(reconciler, old_der, expected):
    """Never revoke a certificate not proven to back all four current Scarlet profiles."""
    if not expected.get("serialNumber"):
        stop("CERTIFICATE_SERIAL_MISSING")
    old_hash=reconciler.sha(old_der)
    roots=sorted(WORK.glob("apple-reconcile-*/Main.mobileprovision"),
                 key=lambda x:x.stat().st_mtime,reverse=True)
    if not roots:
        stop("CURRENT_APPLE_PROFILE_REFERENCES_MISSING")
    folder=roots[0].parent
    devices=original_devices(reconciler)
    for b in BUNDLES:
        label="Main" if b==APP else b.rsplit(".",1)[-1]
        f=folder/(label+".mobileprovision")
        if not f.is_file():
            stop("ORIGINAL_PROFILE_MISSING_"+label)
        p=reconciler.read_profile(f.read_bytes())
        ent=p.get("Entitlements",{})
        certs=set()
        for c in p.get("DeveloperCertificates",[]):
            try:
                certs.add(reconciler.sha(cert_der(bytes(c))))
            except RuntimeError:
                pass
        if (ent.get("application-identifier")!=TEAM+"."+b or
            GROUP not in ent.get("com.apple.security.application-groups",[]) or
            old_hash not in certs or
            not devices.issubset(set(p.get("ProvisionedDevices",[]))) or
            not reconciler.valid_date(p.get("ExpirationDate"))):
            stop("OLD_CERT_NOT_AUTHORIZED_FOR_ALL_FOUR_"+label)
    return folder

def archive_old_public_cert(old, old_der):
    archive=IDENTITY/"revoked-original-public-cert.der"
    if archive.exists() and archive.read_bytes()!=old_der:
        stop("OLD_CERT_ARCHIVE_CONFLICT")
    if not archive.exists():
        archive.write_bytes(old_der)
        archive.chmod(0o600)
    meta=IDENTITY/"revoked-original-certificate-info.json"
    if not meta.exists():
        meta.write_text(json.dumps({
            "team":TEAM,"serialNumber":old["serialNumber"],
            "machineName":str(old.get("machineName") or ""),
            "replacedAt":dt.datetime.now(dt.timezone.utc).isoformat(),
        },indent=2),encoding="utf8")
        meta.chmod(0o600)
    print("[PASS] PUBLIC_OLD_CERT_BACKUP",flush=True)

def certificate_and_key_files(der, local_public):
    if cert_public_key(der)!=local_public:
        stop("NEW_CERT_KEY_MISMATCH")
    normalized=run(["x509","-inform","DER","-outform","PEM"],der)
    if CERT.exists():
        existing=run(["x509","-in",str(CERT),"-outform","DER"])
        if existing!=der:
            stop("EXISTING_NEW_CERT_CHANGED")
    else:
        CERT.write_bytes(normalized)
        CERT.chmod(0o600)
    if not PASSWORD_FILE.exists():
        PASSWORD_FILE.write_text(secrets.token_urlsafe(48),encoding="ascii")
        PASSWORD_FILE.chmod(0o600)
    if not P12.exists():
        run(["pkcs12","-export","-inkey",str(KEY),"-in",str(CERT),
             "-out",str(P12),"-passout","file:"+str(PASSWORD_FILE),
             "-name","Scarlet Crystal V188"])
        P12.chmod(0o600)
    print("[PASS] NEW_P12_KEYPAIR_READY",flush=True)

def enroll_after_revoke(session, local_public, st, reconciler):
    certs=list_certs(session)
    registered=matching_cert(certs,local_public)
    if registered:
        print("[PASS] NEW_APPLE_CERT_ALREADY_REGISTERED",flush=True)
        return registered[1]
    if st.get("csr_submitted"):
        stop("CSR_PREVIOUSLY_SUBMITTED; CHECK_APPLE_PENDING_REQUEST_OR_WAIT")
    if certs:
        stop("OLD_OR_OTHER_CERT_STILL_REGISTERED; NO_NEW_CSR")
    csr=run(["req","-new","-key",str(KEY),"-sha256",
             "-subj","/C=US/O=Scarlet Crystal/CN=Scarlet Crystal V188"])
    st["csr_submitted"]=True
    st["csr_submitted_at"]=dt.datetime.now(dt.timezone.utc).isoformat()
    atomic_json(st)
    print("[CERTIFICATE] Sending one CSR with EXISTING local private key",flush=True)
    reply=session.call("submitDevelopmentCSR",{
        "teamId":TEAM,
        "csrContent":csr.decode("ascii"),
        "machineName":"Scarlet Crystal V188",
        "machineId":str(uuid.uuid4()).upper(),
    },key="certRequest")
    print("[APPLE_CERT_REQUEST_ID_RECEIVED]",bool(reply.get("certRequestId")),flush=True)
    for _ in range(12):
        result=matching_cert(list_certs(session),local_public)
        if result:
            print("[PASS] NEW_APPLE_CERT_ISSUED_AND_KEY_MATCHES",flush=True)
            return result[1]
        time.sleep(3)
    stop("APPLE_CERT_NOT_YET_VISIBLE; DO_NOT_RESUBMIT_CSR")

def download_renewed_profiles(session,apps,der,reconciler):
    old_devices=original_devices(reconciler)
    new_hash=reconciler.sha(der)
    stamp=dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output=IDENTITY/("verified-profiles-"+stamp+"-"+secrets.token_hex(3))
    output.mkdir(parents=True,exist_ok=False,mode=0o700)
    valid=[]
    for b in BUNDLES:
        response=session.call("downloadTeamProvisioningProfile",
                              {"teamId":TEAM,"appIdId":apps[b]["appIdId"]},
                              key="provisioningProfile")
        raw=bytes(response["encodedProfile"])
        data=reconciler.read_profile(raw)
        ent=data.get("Entitlements",{})
        certs=set()
        for c in data.get("DeveloperCertificates",[]):
            try:
                certs.add(reconciler.sha(cert_der(bytes(c))))
            except RuntimeError:
                continue
        status={
            "team_bundle":ent.get("application-identifier")==TEAM+"."+b,
            "original_group":GROUP in ent.get("com.apple.security.application-groups",[]),
            "new_cert":new_hash in certs,
            "same_device":old_devices.issubset(set(data.get("ProvisionedDevices",[]))),
            "not_expired":reconciler.valid_date(data.get("ExpirationDate")),
            "development":ent.get("get-task-allow") is True,
        }
        label="Main" if b==APP else b.rsplit(".",1)[-1]
        file=output/(label+".mobileprovision")
        file.write_bytes(raw)
        file.chmod(0o600)
        ok=all(status.values())
        valid.append(ok)
        print(("[PASS]" if ok else "[BLOCKED]")+" PROFILE_"+label+" "+
              " ".join(k+"="+("1" if v else "0") for k,v in status.items()),
              flush=True)
    print("[PROVISIONING_DIRECTORY]",output,flush=True)
    if not all(valid):
        stop("NEW_PROFILES_NOT_ALL_VALID; NO_IPA_SIGNED")
    print("[PASS] FOUR_PROFILES_AUTHORIZED_FOR_NEW_CERT_AND_APP_GROUP",flush=True)
    print("[P12_PATH]",P12,flush=True)
    print("[P12_PASSWORD_FILE]",PASSWORD_FILE,flush=True)

def main():
    os.umask(0o077)
    if not CA.is_file() or CA.stat().st_size<1000:
        stop("APPLE_CA_BUNDLE_MISSING")
    os.environ["SSL_CERT_FILE"]=str(CA)
    ssl.create_default_context().load_verify_locations(cafile=str(CA))
    api=load_module(BACKEND,"scarlet_pinned_sideinstaller")
    reconciler=load_module(RECONCILER,"scarlet_profile_reader")
    local_public=public_key_local()
    email=input("Apple ID email (local): ").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+",email):
        stop("APPLE_ID_INVALID")
    password=getpass.getpass("Apple ID password (local, hidden): ")
    if not password:
        stop("PASSWORD_MISSING")
    state_dir=HOME/".local/state/scarlet-v187-apple"
    state_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
    anisette,grand=api.connect_anisette(api.FALLBACK_ANISETTE,
                                        str(state_dir/"anisette.json"))
    account=api.AppleAccount(email,grand,anisette)
    try:
        account.login(password,lambda message:re.sub(r"\D","",
                          getpass.getpass(message+" (hidden): ")))
    finally:
        password=None
    token,adsid=account.app_token("xcode.auth")
    session=api.DeveloperSession(account,token,adsid)
    apps=safe_four_app_ids(session)
    certs=list_certs(session)
    st=read_state()
    existing=matching_cert(certs,local_public)
    if existing:
        print("[PASS] REPLACEMENT_CERT_ALREADY_REGISTERED",flush=True)
        certificate_and_key_files(existing[1],local_public)
        download_renewed_profiles(session,apps,existing[1],reconciler)
        return
    if st is None:
        if len(certs)!=1:
            stop("EXPECTED_EXACTLY_ONE_OLD_DEV_CERT; NO_REVOCATION")
        old=certs[0]
        if old.get("certificatePlatform","ios") not in ("ios","iOS","IOS"):
            stop("NOT_IOS_DEVELOPMENT_CERT")
        serial=old.get("serialNumber")
        if not serial or not old.get("certContent"):
            stop("OLD_CERT_SERIAL_OR_PUBLIC_DER_MISSING")
        old_der=cert_der(bytes(old["certContent"]))
        assert_old_cert_used_by_all_four(reconciler,old_der,old)
        archive_old_public_cert(old,old_der)
        st={"team":TEAM,"old_serial":serial,"csr_submitted":False,
            "old_revoke_requested":False}
        atomic_json(st)
    else:
        if st.get("team")!=TEAM or not st.get("old_serial"):
            stop("REPLACEMENT_STATE_CONFLICT")
        if len(certs)>1:
            stop("MULTIPLE_ACTIVE_CERTIFICATES; STOP")
        if certs and certs[0].get("serialNumber")!=st["old_serial"]:
            stop("UNEXPECTED_APPLE_CERT_CHANGE; STOP")
    if certs:
        print("[REVOCATION] Exact old serial, one iOS DEVELOPMENT certificate",flush=True)
        st["old_revoke_requested"]=True
        atomic_json(st)
        session.call("revokeDevelopmentCert",{
            "teamId":TEAM,
            "serialNumber":st["old_serial"],
        })
        print("[PASS] APPLE_REVOKE_REQUEST_ACCEPTED",flush=True)
        for _ in range(8):
            certs=list_certs(session)
            if not any(x.get("serialNumber")==st["old_serial"] for x in certs):
                break
            time.sleep(3)
        if any(x.get("serialNumber")==st["old_serial"] for x in certs):
            stop("OLD_CERT_STILL_PRESENT; DO_NOT_SUBMIT_CSR")
    print("[PASS] OLD_CERT_NO_LONGER_REGISTERED",flush=True)
    new_der=enroll_after_revoke(session,local_public,st,reconciler)
    certificate_and_key_files(new_der,local_public)
    download_renewed_profiles(session,apps,new_der,reconciler)

if __name__=="__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("[STOP] INTERRUPTED; DO_NOT_DELETE_STORED_REPLACEMENT_STATE",file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print("[STOP] CERT_REPLACEMENT",type(exc).__name__,str(exc),file=sys.stderr)
        sys.exit(2)
