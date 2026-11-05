#!/usr/bin/env python3
"""V188 local iOS DEVELOPMENT signing using newly approved Apple P12 + 4 profiles.

Never changes Apple account, certificates, installed apps or original IPA.
Signs in a temporary directory; rejects wrong identity/team/group/bundle IDs.
Development-signed IPA is NOT equivalent to Apple Distribution/Ad Hoc OTA.
"""
import datetime as dt
import hashlib
import os
from pathlib import Path, PurePosixPath
import plistlib
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

HOME=Path.home()
BASE=HOME/".local/share/scarlet-crystal"
IDENTITY=BASE/"signing/identity-v188-enrolled"
P12=IDENTITY/"identity.p12"
PASS=IDENTITY/"identity-password.txt"
KEY=IDENTITY/"private-key.pem"
CERT=IDENTITY/"certificate.pem"
RC=HOME/".local/bin/rcodesign"
OUT=BASE/"v188-signed"
SRC=OUT/"Scarlet-Crystal-V188-NATIVE-RENEWAL-UNSIGNED.ipa"
RESULT=OUT/"Scarlet-Crystal-V188-SIGNED-DEVELOPMENT.ipa"
URL="https://github.com/fx564286/sidestore-auto-refresh/releases/download/scarlet-v188-unsigned-20261105/Scarlet-Crystal-V188-NATIVE-RENEWAL-UNSIGNED.ipa"
EXPECTED_SHA256="5b57a212c29b29a0c74c9387bbd0c875375b34ee1b1cad92af6458b329bacc68"
TEAM="P8EZT3U5N4"
GROUP="group.com.SideStore.SideStore.P8EZT3U5N4"
APP="com.kdt.livecontainer.P8EZT3U5N4"
BUNDLES={"Main":APP,"LiveProcess":APP+".LiveProcess",
         "ShareExtension":APP+".ShareExtension","LaunchAppExtension":APP+".LaunchAppExtension"}

class Blocked(RuntimeError):pass

def require(value,reason):
    if not value:raise Blocked(reason)

def command(args,input=None):
    p=subprocess.run([str(a) for a in args],input=input,stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE,check=False)
    if p.returncode:
        raise Blocked("EXEC_FAILED "+str(args[0])+" "+
                      (p.stderr or p.stdout).decode("utf8","replace")[-1200:])
    return p.stdout

def digest(data):
    return hashlib.sha256(data).hexdigest()

def cert_id():
    require(P12.is_file() and PASS.is_file(),"NEW_P12_OR_PASSWORD_MISSING")
    pem=command(["openssl","pkcs12","-in",P12,"-clcerts","-nokeys",
                 "-passin","file:"+str(PASS)])
    der=command(["openssl","x509","-outform","DER"],pem)
    require(der.startswith(b"0"),"P12_CERTIFICATE_INVALID")
    print("[PASS] NEW_APPLE_P12_KEYPAIR_PRESENT",flush=True)
    return digest(der)

def pem_identity_ready(expected_hash):
    """Use the original enrolled PEM identity directly; bypass rcodesign PFX parser."""
    require(KEY.is_file() and CERT.is_file(),"NEW_APPLE_PEM_IDENTITY_MISSING")
    require(not KEY.is_symlink() and not CERT.is_symlink(),"UNSAFE_PEM_IDENTITY_SYMLINK")
    pem_der=command(["openssl","x509","-in",CERT,"-outform","DER"])
    require(digest(pem_der)==expected_hash,"PEM_CERT_DIFFERS_FROM_APPLE_AUTHORIZED_P12")
    key_pub=command(["openssl","pkey","-in",KEY,"-pubout","-outform","DER"])
    cert_pub_pem=command(["openssl","x509","-in",CERT,"-pubkey","-noout"])
    cert_pub=command(["openssl","pkey","-pubin","-outform","DER"],cert_pub_pem)
    require(key_pub==cert_pub,"APPLE_CERT_PRIVATE_KEY_MISMATCH")
    print("[PASS] APPLE_AUTHORIZED_PEM_CERT_KEY_MATCH",flush=True)

def profile_info(f, bundle, cert_hash):
    raw=command(["openssl","cms","-verify","-inform","DER","-in",f,"-noverify"])
    data=plistlib.loads(raw)
    ent=data.get("Entitlements",{})
    expiration=data.get("ExpirationDate")
    if isinstance(expiration,dt.datetime) and expiration.tzinfo is None:
        expiration=expiration.replace(tzinfo=dt.timezone.utc)
    certs={digest(bytes(c)) for c in data.get("DeveloperCertificates",[])}
    require(ent.get("application-identifier")==TEAM+"."+bundle,
            "APPLE_PROFILE_BUNDLE_MISMATCH_"+bundle)
    require(GROUP in ent.get("com.apple.security.application-groups",[]),
            "APPLE_PROFILE_APP_GROUP_MISSING_"+bundle)
    require(cert_hash in certs,"P12_NOT_AUTHORIZED_BY_APPLE_PROFILE_"+bundle)
    require(bool(data.get("ProvisionedDevices")),
            "DEVICE_NOT_REGISTERED_IN_PROFILE_"+bundle)
    require(isinstance(expiration,dt.datetime) and expiration>dt.datetime.now(dt.timezone.utc),
            "PROFILE_EXPIRED_"+bundle)
    require(ent.get("get-task-allow") is True,
            "EXPECTED_DEVELOPMENT_PROFILE_"+bundle)
    require(isinstance(ent.get("keychain-access-groups"),list)
            and ent["keychain-access-groups"],
            "PROFILE_KEYCHAIN_RIGHTS_MISSING_"+bundle)
    return ent

def profiles(cert_hash):
    folders=sorted(IDENTITY.glob("verified-profiles-*"),
                   key=lambda x:x.stat().st_mtime,reverse=True)
    require(bool(folders),"NO_NEW_APPLE_PROFILES_FOUND")
    for d in folders:
        result={}
        try:
            for label,bundle in BUNDLES.items():
                f=d/(label+".mobileprovision")
                require(f.is_file(),"PROFILE_NOT_FOUND_"+label)
                result[label]=(f,profile_info(f,bundle,cert_hash))
        except (Blocked,ValueError,plistlib.InvalidFileException):
            continue
        if len(result)==4:
            print("[PASS] FOUR_AUTHORIZED_APPLE_PROFILES",d,flush=True)
            return result
    raise Blocked("NO_FOUR_PROFILES_WITH_SAME_NEW_P12_GROUP_AND_DEVICE")

def unsigned():
    if not SRC.is_file():
        temp=SRC.with_name(SRC.name+".partial")
        try:
            with urllib.request.urlopen(URL,timeout=120) as response,temp.open("wb") as out:
                shutil.copyfileobj(response,out,1024*1024)
            require(digest(temp.read_bytes())==EXPECTED_SHA256,
                    "DOWNLOADED_IPA_HASH_MISMATCH")
            temp.replace(SRC)
        finally:
            temp.unlink(missing_ok=True)
    require(digest(SRC.read_bytes())==EXPECTED_SHA256,
            "ORIGINAL_V188_IPA_HASH_MISMATCH")
    print("[PASS] V188_ORIGINAL_SHA256",flush=True)

def unpack(destination):
    with zipfile.ZipFile(SRC) as z:
        files=z.infolist()
        require(len(files)<15000 and sum(i.file_size for i in files)<1500*1024*1024,
                "IPA_ARCHIVE_LIMIT")
        require(z.testzip() is None,"IPA_BAD_ZIP_CRC")
        for i in files:
            p=PurePosixPath(i.filename)
            require(bool(p.parts) and not p.is_absolute() and ".." not in p.parts,
                    "IPA_PATH_TRAVERSAL")
            target=destination.joinpath(*p.parts)
            require(target.resolve(strict=False).is_relative_to(destination.resolve()),
                    "UNSAFE_EXTRACTION_PATH")
            mode=(i.external_attr>>16)&0xFFFF
            if i.is_dir():
                target.mkdir(parents=True,exist_ok=True)
                continue
            target.parent.mkdir(parents=True,exist_ok=True)
            if stat.S_ISLNK(mode):
                link=z.read(i).decode("utf8")
                require(not os.path.isabs(link) and "\x00" not in link
                        and (target.parent/link).resolve(strict=False).is_relative_to(destination.resolve()),
                        "UNSAFE_IPA_SYMLINK")
                target.symlink_to(link)
            else:
                with z.open(i) as source,target.open("wb") as out:
                    shutil.copyfileobj(source,out)
                if mode:target.chmod(stat.S_IMODE(mode))

def restore_ids(payload):
    require(payload.is_dir(),"IPA_PAYLOAD_MISSING")
    roots=[x for x in payload.iterdir() if x.suffix==".app" and x.is_dir()]
    require(len(roots)==1,"EXPECTED_ONE_HOST_APP")
    host=roots[0]
    info=host/"Info.plist"
    original=plistlib.loads(info.read_bytes())
    require(original.get("CFBundleIdentifier")=="com.kdt.livecontainer",
            "V188_UPSTREAM_HOST_ID_UNEXPECTED")
    require(original.get("CFBundleExecutable"),"HOST_EXECUTABLE_MISSING")
    original["CFBundleIdentifier"]=APP
    info.write_bytes(plistlib.dumps(original,sort_keys=False))
    plug=host/"PlugIns"
    require(plug.is_dir(),"THREE_EXTENSIONS_MISSING")
    exts={}
    for folder in plug.glob("*.appex"):
        file=folder/"Info.plist"
        require(file.is_file(),"EXTENSION_INFO_MISSING")
        data=plistlib.loads(file.read_bytes())
        previous=data.get("CFBundleIdentifier","")
        require(previous.startswith("com.kdt.livecontainer."),"UNEXPECTED_EXTENSION_ID")
        name=previous.rsplit(".",1)[-1]
        require(name in BUNDLES and name!="Main" and name not in exts,
                "UNEXPECTED_EXTENSION_NAME")
        data["CFBundleIdentifier"]=BUNDLES[name]
        file.write_bytes(plistlib.dumps(data,sort_keys=False))
        exts[name]=folder
    require(set(exts)==set(BUNDLES)-{"Main"},"NOT_THREE_EXPECTED_EXTENSIONS")
    print("[PASS] FOUR_EXISTING_BUNDLE_IDENTIFIERS_RESTORED",flush=True)
    return host,exts

def embed(host,exts,rights,staging):
    for label,(profile,ent) in rights.items():
        bundle=host if label=="Main" else exts[label]
        shutil.copy2(profile,bundle/"embedded.mobileprovision")
        (staging/(label+".entitlements.plist")).write_bytes(
            plistlib.dumps(ent,fmt=plistlib.FMT_XML,sort_keys=False))
        print("[PASS] APPLE_PROFILE_EMBEDDED",label,flush=True)

def sign(host,exts,staging):
    require(RC.is_file() and os.access(RC,os.X_OK),"RCODESIGN_MISSING")
    helptext=command([RC,"sign","--help"]).decode("utf8","replace")
    for flag in ("--pem-file","--entitlements-xml-file","--shallow"):
        require(flag in helptext,"RCODESIGN_OPTION_UNAVAILABLE_"+flag)
    # OpenSSL 3 exports a PFX that rcodesign 0.29 can reject with a misleading
    # wrong-password error. Apple issued this exact RSA key + PEM certificate;
    # PEM is the native, lossless signing source. No P12 regeneration needed.
    args=[RC,"sign","--pem-file",KEY,"--pem-file",CERT]
    # Deep sign frameworks and other nested binaries first. Then re-sign exact
    # extension entitlements, finally shallow re-seal host resource envelope.
    command(args+[host])
    print("[PASS] NESTED_CODE_SIGNED",flush=True)
    for label in ("LiveProcess","ShareExtension","LaunchAppExtension"):
        command(args+["--shallow","--entitlements-xml-file",
                      staging/(label+".entitlements.plist"),exts[label]])
        print("[PASS] SIGNED_EXTENSION",label,flush=True)
    command(args+["--shallow","--entitlements-xml-file",
                  staging/"Main.entitlements.plist",host])
    print("[PASS] HOST_APP_SIGNED",flush=True)
    for label,path in [("Main",host),*[(x,exts[x]) for x in exts]]:
        command([RC,"verify",path])
        print("[PASS] RCODESIGN_VERIFY",label,flush=True)

def package(staging):
    temp=RESULT.with_name(RESULT.name+".partial")
    try:
        with zipfile.ZipFile(temp,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for f in sorted(staging.rglob("*")):
                if f.is_dir() or (f.parent==staging and f.name.endswith(".entitlements.plist")):
                    continue
                name=f.relative_to(staging).as_posix()
                if f.is_symlink():
                    info=zipfile.ZipInfo(name)
                    info.create_system=3
                    info.external_attr=(stat.S_IFLNK|0o777)<<16
                    z.writestr(info,os.readlink(f).encode())
                else:
                    z.write(f,name,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
        with zipfile.ZipFile(temp) as z:
            require(z.testzip() is None,"SIGNED_IPA_CRC_FAILED")
            files=z.namelist()
            infos=[x for x in files if x.endswith(".appex/Info.plist")
                   or (x.startswith("Payload/") and x.endswith(".app/Info.plist")
                       and "/PlugIns/" not in x)]
            actual={plistlib.loads(z.read(x)).get("CFBundleIdentifier") for x in infos}
            require(len(infos)==4 and actual==set(BUNDLES.values()),
                    "SIGNED_IPA_BUNDLE_IDS_INCORRECT")
            for n in infos:
                require(n.replace("Info.plist","embedded.mobileprovision") in files,
                        "SIGNED_IPA_MISSING_EMBEDDED_PROFILE")
        require(not RESULT.exists(),"SIGNED_IPA_ALREADY_EXISTS_DO_NOT_OVERWRITE")
        temp.replace(RESULT)
    finally:
        temp.unlink(missing_ok=True)

def main():
    os.umask(0o077)
    OUT.mkdir(parents=True,exist_ok=True,mode=0o700)
    cert_hash=cert_id()
    pem_identity_ready(cert_hash)
    rights=profiles(cert_hash)
    unsigned()
    with tempfile.TemporaryDirectory(prefix="scarlet-v188-sign-",dir=OUT) as d:
        staging=Path(d)
        unpack(staging)
        host,exts=restore_ids(staging/"Payload")
        embed(host,exts,rights,staging)
        sign(host,exts,staging)
        package(staging)
    final_hash=digest(RESULT.read_bytes())
    (OUT/(RESULT.name+".sha256")).write_text(final_hash+"  "+RESULT.name+"\n")
    print("[PASS] V188_SIGNED_IPA_CREATED",RESULT,flush=True)
    print("[SHA256]",final_hash,flush=True)
    print("[NOTICE] Development-signed, for device-specific install; not Ad Hoc Safari OTA.",flush=True)

if __name__=="__main__":
    try:main()
    except Blocked as e:
        print("[STOP]",e,file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print("[STOP]",type(e).__name__,str(e),file=sys.stderr)
        sys.exit(3)
