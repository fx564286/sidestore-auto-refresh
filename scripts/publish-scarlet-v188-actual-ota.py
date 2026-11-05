#!/usr/bin/env python3
"""Publish the REAL, locally signed Scarlet Crystal V188 IPA and HTTPS OTA manifest.

Run on the CachyOS PC where the V188 signed IPA was actually produced.
The actual IPA is copied to a GitHub release; no new signing or key upload.
Generate the manifest from the *signed* IPA's own Info.plist, never an assumed
version. No WebClip/mobileconfig profile is generated.
WARN: this is an Apple Development-signed IPA. iOS may reject Safari OTA for
development provisioning. OTA link creation is NOT proof of installation.
"""
import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO="fx564286/sidestore-auto-refresh"
TAG="scarlet-v188-device-signed-20261105"
NAME="Scarlet-Crystal-V188-SIGNED-DEVELOPMENT.ipa"
FOLDER=Path.home()/".local/share/scarlet-crystal/v188-signed"
IPA=FOLDER/NAME
SHA=FOLDER/(NAME+".sha256")
BUNDLE="com.kdt.livecontainer.P8EZT3U5N4"
TEAM="P8EZT3U5N4"
GROUP="group.com.SideStore.SideStore.P8EZT3U5N4"
EXTENSIONS={"LiveProcess","ShareExtension","LaunchAppExtension"}
MANIFEST="Scarlet-V188-SIGNED-manifest.plist"
DIGEST="Scarlet-V188-SIGNED.sha256"
PAGE="https://fx564286.github.io/sidestore-auto-refresh/scarlet-v188.html"
IPA_URL="https://github.com/"+REPO+"/releases/download/"+TAG+"/"+NAME
MANIFEST_URL="https://fx564286.github.io/sidestore-auto-refresh/"+MANIFEST
OTA_URL="itms-services://?action=download-manifest&url="+MANIFEST_URL

class Stop(RuntimeError): pass
def check(b,m):
    if not b: raise Stop(m)

def command(argv,check_exit=True):
    p=subprocess.run([str(x) for x in argv],capture_output=True,text=True,errors="replace")
    if p.returncode and check_exit:
        raise Stop("COMMAND_FAILED "+str(argv[:3])+" "+(p.stderr or p.stdout)[-700:])
    return p

def profile(data,expected):
    r=subprocess.run(["openssl","cms","-verify","-inform","DER","-noverify"],
                     input=data,capture_output=True)
    check(r.returncode==0,"INVALID_APPLE_PROFILE_CMS")
    p=plistlib.loads(r.stdout)
    e=p.get("Entitlements",{})
    check(e.get("application-identifier")==TEAM+"."+expected,"WRONG_PROFILE_APP_ID")
    check(GROUP in e.get("com.apple.security.application-groups",[]),"ORIGINAL_APP_GROUP_MISSING")
    check(TEAM in p.get("TeamIdentifier",[]),"PROFILE_TEAM_MISMATCH")
    expiry=p.get("ExpirationDate")
    check(isinstance(expiry,dt.datetime),"PROFILE_EXPIRY_MISSING")
    check(expiry.replace(tzinfo=dt.timezone.utc)>dt.datetime.now(dt.timezone.utc),"PROFILE_EXPIRED")
    check(bool(p.get("ProvisionedDevices")),"REGISTERED_DEVICE_MISSING")
    check(e.get("get-task-allow") is True,"NOT_ORIGINAL_DEVELOPMENT_PROFILE")
    return p

def inspect():
    check(IPA.is_file() and IPA.stat().st_size>1000000 and not IPA.is_symlink(),
          "SIGNED_V188_IPA_MISSING")
    check(SHA.is_file(),"SIGNER_SHA256_MISSING")
    actual=hashlib.sha256(IPA.read_bytes()).hexdigest()
    expected=SHA.read_text().split()[0].lower()
    check(len(expected)==64 and actual==expected,"SIGNED_IPA_HASH_MISMATCH")
    with zipfile.ZipFile(IPA) as z:
        check(z.testzip() is None,"SIGNED_IPA_CORRUPT")
        names=set(z.namelist())
        main=[x for x in names if x.startswith("Payload/") and
              x.count(".app/")==1 and x.endswith(".app/Info.plist")]
        check(len(main)==1,"MAIN_APP_INFO_NOT_UNIQUE")
        host=main[0].removesuffix("Info.plist")
        info=plistlib.loads(z.read(main[0]))
        check(info.get("CFBundleIdentifier")==BUNDLE,"WRONG_SIGNED_HOST_BUNDLE")
        profile(z.read(host+"embedded.mobileprovision"),BUNDLE)
        ext_paths=[x for x in names if x.startswith(host+"PlugIns/") and x.endswith(".appex/Info.plist")]
        check(len(ext_paths)==3,"THREE_EXTENSIONS_REQUIRED")
        seen=set()
        for path in ext_paths:
            ext=plistlib.loads(z.read(path))
            ext_id=ext.get("CFBundleIdentifier","")
            check(ext_id.startswith(BUNDLE+"."),"WRONG_EXTENSION_BUNDLE")
            label=ext_id.rsplit(".",1)[-1]
            check(label in EXTENSIONS and label not in seen,"INVALID_EXTENSION")
            profile(z.read(path.removesuffix("Info.plist")+"embedded.mobileprovision"),ext_id)
            seen.add(label)
        check(seen==EXTENSIONS,"MISSING_REQUIRED_EXTENSION")
        version=info.get("CFBundleVersion")
        check(isinstance(version,str) and bool(version.strip()),"APP_BUILD_VERSION_MISSING")
        print("[PASS] SIGNED_IPA_AUTHENTICATED_WITH_FOUR_PROFILES")
        print("[PASS] APP_GROUP_ORIGINAL_AND_TEAM_PRESERVED")
        print("[PASS] IPA_SHA256",actual)
        print("[BUILD_VERSION]",version)
        return version,actual

def gh_api(method,resource,payload=None,allow_not_found=False):
    args=["gh","api","-X",method,"repos/"+REPO+"/"+resource]
    if payload is not None:
        with tempfile.NamedTemporaryFile("w",encoding="utf-8",delete=False) as t:
            json.dump(payload,t)
            temp=Path(t.name)
        try: p=command(args+["--input",str(temp)],check_exit=False)
        finally:temp.unlink(missing_ok=True)
    else:p=command(args,check_exit=False)
    if p.returncode:
        if allow_not_found and ("404" in p.stderr or "Not Found" in p.stderr):
            return None
        raise Stop("GITHUB_API_FAILED "+resource+" "+p.stderr[-700:])
    return json.loads(p.stdout)

def put_page_file(path,data):
    entry=gh_api("GET","contents/"+path+"?ref=gh-pages",allow_not_found=True)
    payload={
        "message":"Publish signed Scarlet Crystal V188 actual Safari OTA manifest",
        "branch":"gh-pages",
        "content":base64.b64encode(data).decode("ascii")
    }
    if entry is not None:payload["sha"]=entry["sha"]
    gh_api("PUT","contents/"+path,payload)
    print("[PASS] GH_PAGES_FILE_PUBLISHED",path)

def main():
    check(shutil.which("gh") is not None,"GH_CLI_NOT_INSTALLED")
    check(shutil.which("openssl") is not None,"OPENSSL_MISSING")
    version,hash_value=inspect()
    auth=command(["gh","auth","status"],check_exit=False)
    check(auth.returncode==0,"GITHUB_LOGIN_REQUIRED; run gh auth login")
    existing=gh_api("GET","releases/tags/"+TAG,allow_not_found=True)
    if existing is None:
        cmd=["gh","release","create",TAG,"-R",REPO,"--target","main",
             "--title","Scarlet Crystal V188 — signed development IPA",
             "--notes","V188 locally signed IPA. Apple Development provisioning (device-specific), original App Group preserved. iOS Safari OTA installation is not guaranteed: for official browser distribution use Ad Hoc/Distribution signing. Public asset contains registered device identifiers from Apple provisioning profiles.",
             "--prerelease"]
        command(cmd)
        print("[PASS] SIGNED_RELEASE_CREATED")
        existing=gh_api("GET","releases/tags/"+TAG)
    names={a.get("name") for a in existing.get("assets",[])}
    if NAME not in names:
        command(["gh","release","upload",TAG,str(IPA),"-R",REPO])
        print("[PASS] SIGNED_IPA_UPLOADED_TO_GITHUB")
    else:
        print("[INFO] RELEASE_ASSET_ALREADY_EXISTS")
        # No destructive overwrite; provide an extra checksum check through API.
        existing=gh_api("GET","releases/tags/"+TAG)
        entry=next(a for a in existing["assets"] if a["name"]==NAME)
        if entry.get("digest"):
            check(entry["digest"]=="sha256:"+hash_value,"REMOTE_ASSET_DIGEST_DIFFERS; STOP")
    plist={"items":[{"assets":[{"kind":"software-package","url":IPA_URL}],
          "metadata":{"bundle-identifier":BUNDLE,"bundle-version":version,
                      "kind":"software","title":"Scarlet Crystal V188"}}]}
    payload=plistlib.dumps(plist,fmt=plistlib.FMT_XML,sort_keys=False)
    put_page_file(MANIFEST,payload)
    put_page_file(DIGEST,(hash_value+"  "+NAME+"\n").encode())
    # The signed asset exists and manifest has been updated. Note GitHub Pages
    # deployment/CDN propagation may lag behind this point.
    print("[PASS] ACTUAL_SIGNED_IPA_AND_OTA_MANIFEST_PUBLISHED")
    print("[SIGNED_IPA_URL]",IPA_URL)
    print("[INSTALL_PAGE]",PAGE)
    print("[ITMS_SERVICES_INSTALL_URL]",OTA_URL)
    print("[NOTICE] APP INSTALL NOT YET VERIFIED ON IPHONE")
    print("[NOTICE] DEVELOPMENT-SIGNED_IPA_MAY_BE_REJECTED_FOR_SAFARI_OTA")

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[STOP]",e,file=sys.stderr)
        sys.exit(2)
