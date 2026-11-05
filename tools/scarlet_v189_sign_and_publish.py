#!/usr/bin/env python3
"""V189 real IPA delivery: fetch verified CI artifact, sign locally, publish true OTA.

Runs only on the original CachyOS PC after the V189 integrated Xcode workflow
passes. Uses the already tested V188 PEM-based rcodesign signing implementation
and the newly enrolled certificate+4 Apple profiles; NEVER changes/revokes certs.
No WebClip, no false claim that Safari accepted development provisioning.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import plistlib
import subprocess
import shutil
import tempfile
import zipfile
import base64
import sys

REPO="fx564286/sidestore-auto-refresh"
BRANCH="fix/scarlet-v189-update-provenance-auth-20261105"
RUN_WORKFLOW=".github/workflows/scarlet-v183-host-logs-ipa-build.yml"
ARTIFACT="Scarlet-Crystal-V189-UPDATE-TRUTH-UNSIGNED"
UNSIGNED=ARTIFACT+".ipa"
SIGNER=Path.home()/".local/share/scarlet-crystal/v188-signed/sign-v188.py"
DEST=Path.home()/".local/share/scarlet-crystal/v189-signed"
SIGNED="Scarlet-Crystal-V189-SIGNED-DEVELOPMENT.ipa"
TAG="scarlet-v189-device-signed-20261105"
MANIFEST="Scarlet-V189-SIGNED-manifest.plist"
SHA_FILE="Scarlet-V189-SIGNED.sha256"
HOST_ID="com.kdt.livecontainer.P8EZT3U5N4"
TEAM="P8EZT3U5N4"
GROUP="group.com.SideStore.SideStore.P8EZT3U5N4"
PAGE="scarlet-v189.html"

class Stop(RuntimeError): pass
def require(condition,reason):
    if not condition: raise Stop(reason)

def cmd(args):
    p=subprocess.run([str(a) for a in args],text=True,stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE,check=False)
    if p.returncode:
        raise Stop("COMMAND_FAILED "+str(args[:3])+" "+(p.stderr or p.stdout)[-700:])
    return p.stdout

def gh_api(url,method="GET",payload=None,missing_ok=False):
    argv=["gh","api","-X",method,url]
    if payload is not None:
        with tempfile.NamedTemporaryFile(mode="w",suffix=".json",delete=False) as f:
            json.dump(payload,f)
            fpath=Path(f.name)
        try:p=subprocess.run(argv+["--input",str(fpath)],capture_output=True,text=True)
        finally:fpath.unlink(missing_ok=True)
    else:p=subprocess.run(argv,capture_output=True,text=True)
    if p.returncode:
        if missing_ok and ("404" in p.stderr or "Not Found" in p.stderr):return None
        raise Stop("GITHUB_API_FAILURE "+url+" "+p.stderr[-600:])
    return json.loads(p.stdout)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def inspect(ipa, expected_label, expected_build):
    with zipfile.ZipFile(ipa) as z:
        require(z.testzip() is None,"IPA_ZIP_CRC_FAILED")
        names=set(z.namelist())
        host=[n for n in names if n.startswith("Payload/") and n.count(".app/")==1 and n.endswith(".app/Info.plist")]
        require(len(host)==1,"IPA_HOST_NOT_UNIQUE")
        root=host[0].removesuffix("Info.plist")
        info=plistlib.loads(z.read(host[0]))
        require(info.get("ScarletBuildLabel")==expected_label,"WRONG_SCARLET_BUILD_LABEL")
        require(info.get("CFBundleVersion")==expected_build,"WRONG_IOS_BUILD_NUMBER")
        if expected_label=="V189":
            require(info.get("ScarletUpdateChannel")=="scarlet-device-signed",
                    "V189_UPDATE_CHANNEL_NOT_PRESENT")
        required_id=HOST_ID if expected_label=="V189-signed" else "com.kdt.livecontainer"
        # The ZIP before signing contains upstream IDs; the signed ZIP has restored IDs.
        return info,root,names

def latest_artifact():
    runs=gh_api("repos/"+REPO+"/actions/runs?branch="+BRANCH+"&per_page=30")
    successful=[r for r in runs.get("workflow_runs",[]) if
                r.get("conclusion")=="success" and r.get("path")==RUN_WORKFLOW and
                r.get("head_branch")==BRANCH]
    require(bool(successful),"NO_SUCCESSFUL_V189_INTEGRATED_XCODE_RUN")
    run=max(successful,key=lambda x:x.get("created_at") or "")
    print("[PASS] V189_XCODE_CI_RUN",run["id"],run.get("head_sha"),flush=True)
    return str(run["id"]),run["head_sha"]

def download(run_id):
    unsigned=DEST/UNSIGNED
    if not unsigned.exists():
        with tempfile.TemporaryDirectory(prefix="scarlet-v189-ci-",dir=DEST) as folder:
            cmd(["gh","run","download",run_id,"-R",REPO,"-n",ARTIFACT,"-D",folder])
            root=Path(folder)
            ipas=list(root.rglob(UNSIGNED))
            metas=list(root.rglob(ARTIFACT+".json"))
            require(len(ipas)==1 and len(metas)==1,"V189_CI_ARTIFACT_FILES_MISSING")
            info=json.loads(metas[0].read_text())
            require(info.get("build")=="V189" and info.get("verified") is True,
                    "V189_BUILD_RECEIPT_INVALID")
            checksum=sha(ipas[0].read_bytes())
            require(checksum==info.get("sha256"),"V189_CI_BUILD_SHA256_MISMATCH")
            inspect(ipas[0],"V189","3.8.203")
            shutil.copy2(ipas[0],unsigned)
            (DEST/(UNSIGNED+".sha256")).write_text(checksum+"  "+UNSIGNED+"\n")
    require((DEST/(UNSIGNED+".sha256")).is_file(),"UNSIGNED_RECEIPT_MISSING")
    digest=(DEST/(UNSIGNED+".sha256")).read_text().split()[0]
    require(sha(unsigned.read_bytes())==digest,"UNSIGNED_LOCAL_SHA256_MISMATCH")
    inspect(unsigned,"V189","3.8.203")
    print("[PASS] V189_UNSIGNED_VERIFIED",digest,flush=True)
    return unsigned,digest

def sign(unsigned,digest):
    result=DEST/SIGNED
    if not result.is_file():
        require(SIGNER.is_file(),"PREVIOUS_V188_PEM_SIGNER_NOT_FOUND")
        spec=importlib.util.spec_from_file_location("scarlet_v188_verified_signer",SIGNER)
        signer=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(signer)
        # Preserve verified PEM signing, restore original four bundle IDs.
        signer.OUT=DEST
        signer.SRC=unsigned
        signer.RESULT=result
        signer.EXPECTED_SHA256=digest
        signer.main()
    require(result.is_file() and result.stat().st_size>1_000_000,"V189_SIGNED_IPA_MISSING")
    info,_,_=inspect(result,"V189","3.8.203")
    require(info["CFBundleIdentifier"]==HOST_ID,"SIGNED_V189_TEAM_BUNDLE_CHANGED")
    sha_path=DEST/(SIGNED+".sha256")
    require(sha_path.is_file(),"SIGNED_V189_SHA256_MISSING")
    real=sha(result.read_bytes())
    require(real==sha_path.read_text().split()[0],"SIGNED_V189_HASH_MISMATCH")
    print("[PASS] V189_SIGNED_LOCAL_PEM_AND_FOUR_PROFILES",real,flush=True)
    return result,real

def publish_page(path,raw):
    api="repos/"+REPO+"/contents/"+path
    old=gh_api(api+"?ref=gh-pages",missing_ok=True)
    payload={"branch":"gh-pages",
             "message":"Publish real signed Scarlet Crystal V189 OTA "+path,
             "content":base64.b64encode(raw).decode("ascii")}
    if old:payload["sha"]=old["sha"]
    gh_api(api,method="PUT",payload=payload)
    print("[PASS] GH_PAGES_PUBLISHED",path,flush=True)

def publish(result,digest,sha_commit):
    rel=gh_api("repos/"+REPO+"/releases/tags/"+TAG,missing_ok=True)
    if rel is None:
        cmd(["gh","release","create",TAG,"-R",REPO,
             "--target",sha_commit,
             "--title","Scarlet Crystal V189 — signed development IPA",
             "--notes","Signed from V189 Xcode integrated source. Development provisioning restricted to registered devices. This is not Apple Distribution/Ad Hoc. IPA upload and install manifest are not proof of successful iPhone installation. Existing bundle IDs and App Group preserved.",
             "--prerelease"])
        rel=gh_api("repos/"+REPO+"/releases/tags/"+TAG)
    matches=[a for a in rel.get("assets",[]) if a.get("name")==SIGNED]
    if matches:
        require(len(matches)==1 and matches[0].get("digest")=="sha256:"+digest,
                "REMOTE_V189_SIGNED_ASSET_CONFLICT")
    else:
        cmd(["gh","release","upload",TAG,str(result),"-R",REPO])
    print("[PASS] SIGNED_V189_IPA_UPLOADED",flush=True)
    ipa_url="https://github.com/"+REPO+"/releases/download/"+TAG+"/"+SIGNED
    manifest={"items":[{"assets":[{"kind":"software-package","url":ipa_url}],
                       "metadata":{"bundle-identifier":HOST_ID,
                                   "bundle-version":"3.8.203",
                                   "kind":"software","title":"Scarlet Crystal V189"}}]}
    publish_page(MANIFEST,plistlib.dumps(manifest,fmt=plistlib.FMT_XML))
    publish_page(SHA_FILE,(digest+"  "+SIGNED+"\n").encode())
    old=gh_api("repos/"+REPO+"/contents/scarlet-v188.html?ref=gh-pages")
    original=base64.b64decode(old["content"]).decode("utf8")
    page=original.replace("scarlet-v188-device-signed-20261105",TAG)
    page=page.replace("Scarlet-V188-SIGNED-manifest.plist",MANIFEST)
    page=page.replace("Scarlet-Crystal-V188-SIGNED-DEVELOPMENT.ipa",SIGNED)
    page=page.replace("V188","V189").replace("v188","v189")
    require("itms-services://" in page and TAG in page and "webClip" not in page,
            "OTA_PAGE_TEMPLATE_INVALID")
    publish_page(PAGE,page.encode("utf8"))
    print("[PASS] V189_ACTUAL_APP_OTA_ASSETS_PUBLISHED",flush=True)
    print("[INSTALL_PAGE] https://fx564286.github.io/sidestore-auto-refresh/"+PAGE,flush=True)
    print("[SIGNED_IPA] "+ipa_url,flush=True)
    print("[NOTICE] DEVELOPMENT_SIGNED_SAFARI_OTA_NOT_GUARANTEED",flush=True)
    print("[NOTICE] IPHONE_INSTALL_AND_LIQUID_GLASS_RUNTIME_NOT_YET_VERIFIED",flush=True)

def main():
    require(shutil.which("gh") is not None,"GITHUB_CLI_MISSING")
    require(SIGNER.is_file(),"LOCAL_TESTED_V188_SIGNER_MISSING")
    DEST.mkdir(parents=True,exist_ok=True,mode=0o700)
    cmd(["gh","auth","status"])
    run,sha_commit=latest_artifact()
    unsigned,digest=download(run)
    signed,signsha=sign(unsigned,digest)
    publish(signed,signsha,sha_commit)

if __name__=="__main__":
    try:main()
    except Exception as error:
        print("[STOP]",str(error),file=sys.stderr)
        sys.exit(2)
