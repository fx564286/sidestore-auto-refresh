#!/usr/bin/env python3
"""Scarlet Crystal: reusable version-independent IPA signing and Safari publishing.

Run on the CachyOS PC that holds the *existing* Apple-approved PEM key and four
provisioning profiles. Finds verified, successful Xcode integration artifacts in
this owner's repository, chooses the highest Scarlet release number and actual
CFBundleVersion, signs locally with the known V188 PEM signer, and publishes
the genuine signed IPA + OTA plist + SHA256 + versioned and fixed 'latest' pages.

Does not revoke certificates, delete apps, publish secrets or install on iPhone.
A DEVELOPMENT-signed IPA is NOT an Ad Hoc distribution build; Safari may reject it.
The last stdout line is an install-page HTTPS URL ONLY after every step passes.
"""
from __future__ import annotations
import base64
import contextlib
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO="fx564286/sidestore-auto-refresh"
WORKFLOW="scarlet-v183-host-logs-ipa-build.yml"
ARTIFACT_RE=re.compile(r"^Scarlet-Crystal-V([0-9]+)-[A-Za-z0-9_-]+-UNSIGNED$")
TAG_RE=re.compile(r"^scarlet-v([0-9]+)-device-signed-([0-9]{8})$")
HOST_ID="com.kdt.livecontainer.P8EZT3U5N4"
RAW_HOST_ID="com.kdt.livecontainer"
TEAM="P8EZT3U5N4"
GROUP="group.com.SideStore.SideStore.P8EZT3U5N4"
EXTENSIONS={"LiveProcess","ShareExtension","LaunchAppExtension"}
BASE=Path.home()/".local/share/scarlet-crystal"
OUT=BASE/"latest-publisher"
SIGNER=BASE/"v188-signed/sign-v188.py"
IDENTITY=BASE/"signing/identity-v188-enrolled"
PAGES="https://fx564286.github.io/sidestore-auto-refresh"
LATEST_PAGE=PAGES+"/scarlet-latest.html"
MAX_VARIANTS=4

class Halt(RuntimeError):
    pass

def require(condition,message):
    if not condition:raise Halt(message)

def log(*args):
    print(*args,file=sys.stderr,flush=True)

def call(args, timeout=180):
    p=subprocess.run([str(v) for v in args],text=True,capture_output=True,
                     errors="replace",timeout=timeout)
    if p.returncode:
        raise Halt("COMMAND_FAILED "+str(args[:3])+" "+(p.stderr or p.stdout)[-900:])
    return p.stdout

def gh_api(path,method="GET",data=None,missing=False):
    argv=["gh","api","--method",method,path]
    if data is not None:
        with tempfile.NamedTemporaryFile(mode="w",delete=False,encoding="utf8") as f:
            json.dump(data,f)
            tmp=Path(f.name)
        try:
            p=subprocess.run(argv+["--input",str(tmp)],text=True,capture_output=True)
        finally:
            tmp.unlink(missing_ok=True)
    else:
        p=subprocess.run(argv,text=True,capture_output=True)
    if p.returncode:
        if missing and ("404" in p.stderr or "Not Found" in p.stderr):
            return None
        raise Halt("GITHUB_API "+path+" "+p.stderr[-600:])
    return json.loads(p.stdout)

def hashfile(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        while b:=f.read(1024*1024):h.update(b)
    return h.hexdigest()

def releases():
    records=gh_api("repos/"+REPO+"/releases?per_page=100")
    result=[]
    for row in records:
        matched=TAG_RE.fullmatch(row.get("tag_name",""))
        if matched and not row.get("draft"):
            result.append((int(matched[1]),row))
    return result

def published_release(version):
    matches=[row for n,row in releases() if n==version]
    return max(matches,key=lambda x:x.get("published_at") or "") if matches else None

def release_is_usable(row,version):
    if row is None:return False
    target=f"Scarlet-Crystal-V{version}-SIGNED-DEVELOPMENT.ipa"
    assets=[a for a in row.get("assets",[]) if a.get("name")==target
            and a.get("state")=="uploaded" and int(a.get("size") or 0)>1_000_000]
    return len(assets)==1 and bool(re.fullmatch(r"sha256:[0-9a-f]{64}",
                                             assets[0].get("digest") or ""))

def find_candidates():
    doc=gh_api("repos/"+REPO+"/actions/workflows/"+WORKFLOW+
               "/runs?status=success&per_page=100")
    runs=[r for r in doc.get("workflow_runs",[]) if
          r.get("conclusion")=="success"
          and r.get("event") in ("push","workflow_dispatch")
          and (r.get("head_repository") or {}).get("full_name")==REPO
          and r.get("path","").endswith("/"+WORKFLOW)]
    runs.sort(key=lambda row:row.get("created_at") or "",reverse=True)
    ranked={}
    for run in runs:
        artifacts=gh_api("repos/"+REPO+"/actions/runs/"+str(run["id"])+
                         "/artifacts?per_page=100")
        for a in artifacts.get("artifacts",[]):
            match=ARTIFACT_RE.fullmatch(a.get("name",""))
            if not match or a.get("expired") or a.get("size_in_bytes",0)<1_000_000:continue
            version=int(match[1])
            ranked.setdefault(version,[]).append((run,a))
    if not ranked:raise Halt("NO_VALID_SUCCESSFUL_SCARLET_IPA_ARTIFACT")
    version=max(ranked)
    return version,ranked[version][:MAX_VARIANTS]

def read_meta(ipa, version):
    with zipfile.ZipFile(ipa) as z:
        require(z.testzip() is None,"ZIP_CRC_FAILED")
        names=set(z.namelist())
        main=[p for p in names if p.startswith("Payload/") and
              p.count(".app/")==1 and p.endswith(".app/Info.plist")]
        require(len(main)==1,"SINGLE_HOST_APP_NOT_FOUND")
        root=main[0].removesuffix("Info.plist")
        info=plistlib.loads(z.read(main[0]))
        require(info.get("ScarletBuildLabel")==f"V{version}","WRONG_SCARLET_BUILD_LABEL")
        require(info.get("CFBundleIdentifier")==RAW_HOST_ID,"UNSIGNED_UPSTREAM_ID_MISMATCH")
        require(info.get("CFBundleDisplayName")=="Scarlet Crystal","SCARLET_BRANDING_MISSING")
        build=info.get("CFBundleVersion")
        require(isinstance(build,str) and bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)*",build)),
                "CFBUNDLEVERSION_INVALID")
        exts=[p for p in names if p.startswith(root+"PlugIns/") and p.endswith(".appex/Info.plist")]
        found={plistlib.loads(z.read(p)).get("CFBundleIdentifier","").rsplit(".",1)[-1]
               for p in exts}
        require(found==EXTENSIONS,"EXTENSIONS_CHANGED")
        require(root+"Frameworks/SideStoreApp.framework/SideStore" in names,
                "EMBEDDED_SIDESTORE_MISSING")
        return build

def version_tuple(build):
    return tuple(int(part) for part in build.split("."))

def download_candidate(run,artifact):
    name=artifact["name"]
    folder=OUT/("run-"+str(run["id"])+"-"+name)
    folder.mkdir(parents=True,exist_ok=True)
    ipa=folder/(name+".ipa")
    meta=folder/(name+".json")
    if not ipa.is_file() or not meta.is_file():
        call(["gh","run","download",str(run["id"]),"-R",REPO,
              "-n",name,"-D",str(folder)],timeout=210)
    require(ipa.is_file() and meta.is_file(),"CI_UNSIGNED_IPA_OR_RECEIPT_MISSING")
    doc=json.loads(meta.read_text())
    version=int(ARTIFACT_RE.fullmatch(name)[1])
    require(doc.get("verified") is True and doc.get("build")==f"V{version}",
            "CI_BUILD_RECEIPT_INVALID")
    actual=hashfile(ipa)
    require(doc.get("sha256")==actual,"CI_ARTIFACT_SHA256_MISMATCH")
    build=read_meta(ipa,version)
    return (version_tuple(build),run["created_at"],ipa,build,actual,run["head_sha"])

def choose_artifact(candidates):
    good=[]
    for run,a in candidates:
        try:
            good.append(download_candidate(run,a))
        except Exception as e:
            log("[REJECT] INVALID_CI_ARTIFACT run=",run.get("id"),type(e).__name__,str(e)[:160])
    require(bool(good),"NO_VERIFIED_CI_VARIANT")
    chosen=max(good,key=lambda t:(t[0],t[1]))
    log("[PASS] CI_UNSIGNED_VERIFIED build="+chosen[3]+" sha256="+chosen[4])
    return chosen

def inspect_signed(ipa,version,build):
    with zipfile.ZipFile(ipa) as z:
        require(z.testzip() is None,"SIGNED_ZIP_CRC_FAILED")
        names=set(z.namelist())
        main=[p for p in names if p.startswith("Payload/") and
              p.count(".app/")==1 and p.endswith(".app/Info.plist")]
        require(len(main)==1,"SIGNED_MAIN_INFO_MISSING")
        root=main[0].removesuffix("Info.plist")
        info=plistlib.loads(z.read(main[0]))
        require(info.get("CFBundleIdentifier")==HOST_ID,"SIGNED_HOST_BUNDLE_ID_MISMATCH")
        require(info.get("ScarletBuildLabel")==f"V{version}","SIGNED_BUILD_LABEL_MISMATCH")
        require(info.get("CFBundleVersion")==build,"SIGNED_BUILD_NUMBER_MISMATCH")
        seen=set()
        for label,bundle in [("Main",HOST_ID),*[(x,HOST_ID+"."+x) for x in EXTENSIONS]]:
            if label=="Main":base=root
            else:
                paths=[p.removesuffix("Info.plist") for p in names
                       if p.startswith(root+"PlugIns/") and p.endswith(".appex/Info.plist")
                       and plistlib.loads(z.read(p)).get("CFBundleIdentifier")==bundle]
                require(len(paths)==1,"MISSING_SIGNED_EXTENSION_"+label)
                base=paths[0]
            prof=base+"embedded.mobileprovision"
            require(prof in names,"MISSING_APPLE_PROVISION_"+label)
            r=subprocess.run(["openssl","cms","-verify","-inform","DER","-noverify"],
                             input=z.read(prof),capture_output=True)
            require(r.returncode==0,"CMS_PROFILE_MALFORMED_"+label)
            p=plistlib.loads(r.stdout)
            ent=p.get("Entitlements",{})
            require(ent.get("application-identifier")==TEAM+"."+bundle,
                    "PROFILE_WRONG_BUNDLE_"+label)
            require(GROUP in ent.get("com.apple.security.application-groups",[]),
                    "PROFILE_APP_GROUP_MISSING_"+label)
            require(bool(p.get("ProvisionedDevices")),"PROFILE_NO_DEVICE_"+label)
            expiration=p.get("ExpirationDate")
            require(isinstance(expiration,dt.datetime),"PROFILE_EXPIRATION_MISSING_"+label)
            require(expiration.replace(tzinfo=dt.timezone.utc)>
                    dt.datetime.now(dt.timezone.utc),"PROFILE_EXPIRED_"+label)
            seen.add(label)
        require(len(seen)==4,"NOT_ALL_SIGNED_PROFILES_PRESENT")
        return info

def signing(ipa,version,build,digest):
    result=OUT/(f"Scarlet-Crystal-V{version}-SIGNED-DEVELOPMENT.ipa")
    if not result.is_file():
        require(SIGNER.is_file(),"PREVIOUS_VERIFIED_PEM_SIGNER_MISSING")
        require((IDENTITY/"private-key.pem").is_file() and
                (IDENTITY/"certificate.pem").is_file(),"APPLE_IDENTITY_NOT_ON_THIS_PC")
        module=importlib.util.spec_from_file_location("scarlet_signer",SIGNER)
        signer=importlib.util.module_from_spec(module)
        module.loader.exec_module(signer)
        signer.OUT=OUT
        signer.SRC=ipa
        signer.RESULT=result
        signer.EXPECTED_SHA256=digest
        # The iOS Shortcuts SSH result MUST be one valid HTTPS URL only.
        # Send all progress from the reused signer to stderr, never stdout.
        # The shell wrapper stores stderr in last-run.log.
        with contextlib.redirect_stdout(sys.stderr):
            signer.main()
    require(result.is_file() and result.stat().st_size>1_000_000,"SIGNED_IPA_NOT_CREATED")
    info=inspect_signed(result,version,build)
    sha_path=OUT/(result.name+".sha256")
    require(sha_path.is_file(),"SIGNER_SHA256_MISSING")
    signed_hash=hashfile(result)
    require(signed_hash==sha_path.read_text().split()[0].lower(),"SIGNED_HASH_INVALID")
    log("[PASS] SIGNED_IPA_FOUR_PROFILES_APP_GROUP",signed_hash)
    return result,signed_hash

def publish_pages_file(path,data):
    resource="repos/"+REPO+"/contents/"+path
    existing=gh_api(resource+"?ref=gh-pages",missing=True)
    if existing is not None and base64.b64decode(existing["content"])==data:
        return
    payload={"branch":"gh-pages",
             "message":"Publish real Scarlet Crystal signed IPA install asset "+path,
             "content":base64.b64encode(data).decode("ascii")}
    if existing:payload["sha"]=existing["sha"]
    gh_api(resource,method="PUT",data=payload)
    log("[PASS] PAGES_UPDATED",path)

def publish_release(result,signed_hash,version,head_sha):
    old=published_release(version)
    tag=(old or {}).get("tag_name") or (
        "scarlet-v"+str(version)+"-device-signed-"+
        dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d"))
    release=gh_api("repos/"+REPO+"/releases/tags/"+tag,missing=True)
    if release is None:
        call(["gh","release","create",tag,"-R",REPO,
              "--target",head_sha,
              "--title",f"Scarlet Crystal V{version} — signed development IPA",
              "--notes","Real SHA-256 verified signed IPA from owner CI. "
                        "Apple Development provisioning restricts supported iPhones; "
                        "Safari OTA may refuse this type of provisioning. "
                        "App data and Liquid Glass runtime must be verified on-device.",
              "--prerelease"])
        release=gh_api("repos/"+REPO+"/releases/tags/"+tag)
    assets=[a for a in release.get("assets",[]) if a.get("name")==result.name]
    if assets:
        require(len(assets)==1 and assets[0].get("digest")=="sha256:"+signed_hash,
                "PUBLISHED_ASSET_HAS_DIFFERENT_SHA256")
    else:
        call(["gh","release","upload",tag,str(result),"-R",REPO],timeout=240)
        release=gh_api("repos/"+REPO+"/releases/tags/"+tag)
        assets=[a for a in release.get("assets",[]) if a.get("name")==result.name]
        require(len(assets)==1 and assets[0].get("digest")=="sha256:"+signed_hash,
                "PUBLISHED_ASSET_SHA256_NOT_CONFIRMED")
    return tag

def pages(version,build,result,digest,tag):
    name=result.name
    ipa_url="https://github.com/"+REPO+"/releases/download/"+tag+"/"+name
    mname=f"Scarlet-V{version}-SIGNED-manifest.plist"
    hname=f"Scarlet-V{version}-SIGNED.sha256"
    manifest={"items":[{"assets":[{"kind":"software-package","url":ipa_url}],
                        "metadata":{"bundle-identifier":HOST_ID,"bundle-version":build,
                                    "kind":"software","title":f"Scarlet Crystal V{version}"}}]}
    publish_pages_file(mname,plistlib.dumps(manifest,fmt=plistlib.FMT_XML))
    publish_pages_file(hname,(digest+"  "+name+"\n").encode())
    # The V189 real-app page already verifies release asset + manifest + SHA256.
    template=gh_api("repos/"+REPO+"/contents/scarlet-v189.html?ref=gh-pages")
    src=base64.b64decode(template["content"]).decode("utf8")
    html=src.replace("scarlet-v189-device-signed-20261105",tag)
    html=html.replace("Scarlet-Crystal-V189-SIGNED-DEVELOPMENT.ipa",name)
    html=html.replace("Scarlet-V189-SIGNED-manifest.plist",mname)
    html=html.replace("Scarlet-V189-SIGNED.sha256",hname)
    html=html.replace("3.8.203",build)
    html=html.replace("V189",f"V{version}").replace("v189",f"v{version}")
    require(tag in html and name in html and mname in html
            and "itms-services://" in html and "checksum mismatch" in html,
            "SIGNED_INSTALL_PAGE_INTEGRITY_GUARD_MISSING")
    require("com.apple.webClip.managed" not in html,"WEBCLIP_PROHIBITED")
    publish_pages_file(f"scarlet-v{version}.html",html.encode("utf8"))
    publish_pages_file("scarlet-latest.html",html.encode("utf8"))
    # Updating the main index or re-signing an unrelated app is out of scope.
    log("[PASS] REAL_V"+str(version)+"_SAFARI_INSTALL_PAGE_PUBLISHED")
    log("[NOTICE] Safari OTA use of Apple Development IPA is not guaranteed")
    log("[NOTICE] iPhone installation, app data and Liquid Glass remain unverified")

def main():
    os.umask(0o077)
    require(os.geteuid()!=0,"DO_NOT_RUN_AS_ROOT")
    require(shutil.which("gh") and shutil.which("openssl"),"GITHUB_CLI_OR_OPENSSL_MISSING")
    OUT.mkdir(parents=True,exist_ok=True,mode=0o700)
    call(["gh","auth","status"])
    latest_version,candidates=find_candidates()
    done=[(v,r) for v,r in releases() if release_is_usable(r,v)]
    if done and max(v for v,_ in done)>latest_version:
        raise Halt("SIGNED_RELEASE_NEWER_THAN_CI; DO_NOT_DOWNGRADE")
    if done and max(v for v,_ in done)==latest_version:
        # A signed release exists; ensure a corresponding trusted page exists,
        # instead of re-signing an unchanged build from this device.
        page=gh_api("repos/"+REPO+"/contents/scarlet-latest.html?ref=gh-pages",missing=True)
        require(page is not None,"SIGNED_RELEASE_EXISTS_BUT_LATEST_PAGE_MISSING")
        log("[PASS] ALREADY_PUBLISHED_SIGNED_LATEST_V"+str(latest_version))
        print(LATEST_PAGE)
        return
    (_,_,ipa,build,digest,sha)=choose_artifact(candidates)
    result,signed_hash=signing(ipa,latest_version,build,digest)
    tag=publish_release(result,signed_hash,latest_version,sha)
    pages(latest_version,build,result,signed_hash,tag)
    # Stable output for iOS Shortcuts "Open URLs" action; never print on failure.
    print(LATEST_PAGE)

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        log("[STOP]",type(exc).__name__,str(exc))
        sys.exit(2)
