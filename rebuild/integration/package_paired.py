#!/usr/bin/env python3
"""Package pinned built LC + SideStore together, using official dylibify mechanics.

Engine-level integration proof only. No device signing, no host SwiftUI
redesign claim. Never installs, revokes, deletes app or modifies profile.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tarfile
import zipfile

HOST_ID="com.kdt.livecontainer.P8EZT3U5N4"
EXTENSIONS=("LiveProcess","ShareExtension","LaunchAppExtension")

def call(*args):
    print("[RUN]", " ".join(map(str,args)),flush=True)
    subprocess.run([str(x) for x in args],check=True)

def read(path):
    with Path(path).open("rb") as fp: return plistlib.load(fp)

def write(path,value):
    with Path(path).open("wb") as fp: plistlib.dump(value,fp,sort_keys=False)

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as fp:
        for block in iter(lambda:fp.read(1048576),b""):h.update(block)
    return h.hexdigest()

def ipa(payloadroot,out):
    out.parent.mkdir(parents=True,exist_ok=True)
    call("ditto","-c","-k","--keepParent",payloadroot,out)
    assert out.is_file() and out.stat().st_size>1000000

def cleanup_codesign(app):
    for p in list(app.rglob("_CodeSignature")):
        if p.is_dir():shutil.rmtree(p)
    for p in list(app.rglob("embedded.mobileprovision")):
        p.unlink()

def append_unique(seq,item):
    if item not in seq:seq.append(item)

def side_urls(info):
    arr=info.setdefault("CFBundleURLTypes",[])
    names={x for obj in arr for x in obj.get("CFBundleURLSchemes",[])}
    for label,scheme in [("com.kdt.livecontainer.sidestoreurlscheme","sidestore"),
                          ("com.kdt.livecontainer.sidestorebackupurlscheme","sidestore-com.kdt.livecontainer")]:
        if scheme not in names:
            arr.append(dict(CFBundleURLName=label,CFBundleURLSchemes=[scheme]))
    # For interoperability this is an Info.plist declaration, not authorization
    # to use the actual SideStore App Group in a provisioning profile.
    groups=info.setdefault("ALTAppGroups",[])
    append_unique(groups,"group.com.SideStore.SideStore")
    intents=info.setdefault("INIntentsSupported",[])
    for n in ("RefreshAllIntent","ViewAppIntent"):append_unique(intents,n)
    activities=info.setdefault("NSUserActivityTypes",[])
    for n in ("RefreshAllIntent","ViewAppIntent"):append_unique(activities,n)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--lc-tar",type=Path,required=True)
    p.add_argument("--sidestore-ipa",type=Path,required=True)
    p.add_argument("--lc-appinfo",type=Path,required=True)
    p.add_argument("--dylibify",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--host-report",type=Path)
    p.add_argument("--side-auth-report",type=Path)
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    work=args.out/"_build_work"
    if work.exists():shutil.rmtree(work)
    lcroot=work/"lc"
    lcroot.mkdir(parents=True)
    call("tar","-xf",args.lc_tar,"-C",lcroot)
    original=lcroot/"LiveContainer.app"
    assert original.is_dir()
    side=work/"side"
    with zipfile.ZipFile(args.sidestore_ipa) as z:z.extractall(side)
    sideapp=side/"Payload/SideStore.app"
    assert sideapp.is_dir()
    assert (original/"Frameworks/SideStoreSupport.framework").is_dir()
    assert args.lc_appinfo.is_file()
    assert args.dylibify.is_file()

    # Standalone app is a separate diagnostic artifact. Preserve three LC
    # extensions and original upstream signing behavior for later comparison.
    standalone=work/"standalone"/"Payload"/"LiveContainer.app"
    standalone.parent.mkdir(parents=True)
    shutil.copytree(original,standalone,symlinks=True)
    shutil.rmtree(standalone/"Frameworks/SideStoreSupport.framework")
    info=read(standalone/"Info.plist")
    info["CFBundleIdentifier"]=HOST_ID
    info["CFBundleDisplayName"]="Scarlet Crystal (Engine Diagnostic)"
    write(standalone/"Info.plist",info)
    for ext in EXTENSIONS:
        f=standalone/"PlugIns"/(ext+".appex")/"Info.plist"
        ei=read(f)
        ei["CFBundleIdentifier"]=HOST_ID+"."+ext
        write(f,ei)
    cleanup_codesign(standalone)
    standalone_ipa=args.out/"Scarlet-LiveContainer-Engine-UNSIGNED.ipa"
    ipa(standalone.parent,standalone_ipa)

    # Combined LC+SideStore: clone from the same built native app.
    combined=work/"combined"/"Payload"/"LiveContainer.app"
    combined.parent.mkdir(parents=True)
    shutil.copytree(original,combined,symlinks=True)
    info=read(combined/"Info.plist")
    info["CFBundleIdentifier"]=HOST_ID
    info["CFBundleDisplayName"]="Scarlet Crystal"
    side_urls(info)
    write(combined/"Info.plist",info)
    for ext in EXTENSIONS:
        f=combined/"PlugIns"/(ext+".appex")/"Info.plist"
        ei=read(f)
        ei["CFBundleIdentifier"]=HOST_ID+"."+ext
        write(f,ei)
    framework=combined/"Frameworks"/"SideStoreApp.framework"
    assert not framework.exists(),"Unexpected existing SideStoreApp.framework"
    shutil.copytree(sideapp,framework,symlinks=True)

    # The original LC upstream integration explicitly uses dylibify before
    # loading SideStore as a guest framework. Merely embedding SideStore.app
    # without converting Mach-O will NOT make it usable.
    binary=framework/"SideStore"
    dylib=framework/"SideStore.dylib"
    assert binary.is_file()
    call(args.dylibify,binary,dylib)
    assert dylib.is_file() and dylib.stat().st_size>100000
    binary.unlink()
    dylib.rename(binary)
    call("ldid","-S",binary)
    shutil.copy2(args.lc_appinfo,framework/"LCAppInfo.plist")

    # Preserve SideStore Shortcuts refresh metadata in host as upstream does.
    for file in ("Intents.intentdefinition","ViewApp.intentdefinition"):
        obj=framework/file
        assert obj.is_file(),f"SideStore refresh intent file missing: {file}"
        shutil.copy2(obj,combined/file)
    metadata=framework/"Metadata.appintents"
    assert metadata.exists(),"SideStore metadata missing"
    target=combined/"Metadata.appintents"
    if target.exists():shutil.rmtree(target)
    shutil.copytree(metadata,target,symlinks=True)
    binary_metadata=target/"extract.actionsdata"
    assert binary_metadata.is_file(),"Refresh shortcut metadata missing"
    content=binary_metadata.read_bytes()
    content=content.replace(b"9SideStore20RefreshAllAppsIntentV",
                            b"16SideStoreSupport20RefreshAllAppsIntentV")
    content=content.replace(b"9SideStore26RefreshAllAppsWidgetIntentV",
                            b"16SideStoreSupport26RefreshAllAppsWidgetIntentV")
    binary_metadata.write_bytes(content)

    # Optional SideStore widget requires a fifth provisioning profile, which
    # this user's Personal Team has not authorized. Fail closed on new
    # extensions rather than silently adding unknown app identities.
    widgets=framework/"PlugIns"
    widget_discarded=False
    if widgets.exists():
        known=sorted(x.name for x in widgets.glob("*.appex"))
        assert all(x=="AltWidgetExtension.appex" for x in known),known
        if known:
            shutil.rmtree(widgets)
            widget_discarded=True

    settings=combined/"Settings.bundle/Root.plist"
    if settings.is_file():
        obj=read(settings)
        rows=obj.setdefault("PreferenceSpecifiers",[])
        if not any(row.get("Key")=="LCOpenSideStore" for row in rows):
            rows.append(dict(Type="PSToggleSwitchSpecifier",Title="Open SideStore",
                             Key="LCOpenSideStore",DefaultValue=False))
        write(settings,obj)

    cleanup_codesign(combined)
    combined_ipa=args.out/"Scarlet-LiveContainer+SideStore-ENGINES-UNSIGNED.ipa"
    ipa(combined.parent,combined_ipa)
    side_copy=args.out/"SideStore-Standalone-UNSIGNED.ipa"
    shutil.copy2(args.sidestore_ipa,side_copy)

    host_proof=json.loads(args.host_report.read_text()) if args.host_report and args.host_report.is_file() else {}
    auth_proof=json.loads(args.side_auth_report.read_text()) if args.side_auth_report and args.side_auth_report.is_file() else {}
    assert auth_proof.get("onlyNavigationEntryPatched") is True, "Native SideStore login entry report missing"
    assert auth_proof.get("originalTwoFactorUIUnmodified") is True, "Cannot verify original 2FA remains unchanged"
    assert auth_proof.get("sameFileNativeSignInForwarder") is True, "Original SideStore native login forwarder missing"
    assert auth_proof.get("loginColdLaunchDeferralEnabled") is True, "SideStore cold-launch login readiness check missing"
    report={
        "schema":1,"hostBundleID":HOST_ID,
        "threeOriginalExtensions":list(EXTENSIONS),
        "separateEngineIPAs":True,"embeddedSideStore":True,
        "nativeSideStoreSupport":True,"sourceProvenancePinned":True,
        "upstreamDylibifySHA256":sha256(args.dylibify),
        "sideStoreWidgetExcludedPendingFifthProfile":widget_discarded,
        "retainsIntentsMetadata":True,"codesignedWithAppleProfile":False,
        "userDeviceInstallationVerified":False,
        "sideStoreAppleAuthenticationVerified":False,
        "nativeSideStoreSignInDeepLink":auth_proof.get("nativeSignInDeepLink"),
        "originalSideStoreAuthFlowPreserved":True,
        "loginDeviceVerified":False,
        "authAdapterAudit":auth_proof,
        "FigmaScarletShellSourceCompiled":bool(host_proof.get("newRootCompiled",False)),
        "originalNativeGlassSourceCompiled":bool(host_proof.get("newRootCompiled",False)),
        "hostIntegrationHashes":host_proof.get("sources",[]),
        "nativeOriginalLiquidGlassVerified":False,
        "scope":"Engine diagnostics only; NOT a release or a confirmed functional app",
        "files":{p.name:{"bytes":p.stat().st_size,"sha256":sha256(p)}
                 for p in (standalone_ipa,side_copy,combined_ipa)}
    }
    (args.out/"integrated-build-report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("[PASS] Built two separate engine IPAs and one combined engine IPA")
    print("[BLOCK] Apple signing, on-device install, Figma UI and native Liquid Glass not yet verified")
    shutil.rmtree(work)
if __name__=="__main__":main()
