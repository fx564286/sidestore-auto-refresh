#!/usr/bin/env python3
"""Audit real upstream iOS binaries, module provenance and two distinct install paths.

A successful Xcode build is not user-device installation, entitlement
authorization, pairing/Apple ID authentication or signed release proof.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import plistlib
import subprocess
import zipfile
from datetime import datetime,timezone

HOST_ID="com.kdt.livecontainer.P8EZT3U5N4"
EXTENSIONS=("LiveProcess","ShareExtension","LaunchAppExtension")
ROOT=Path(__file__).resolve().parents[2]
PINS=json.loads((ROOT/"config/scarlet-upstream-pins.json").read_text())

def git(repo,*args):
    return subprocess.check_output(["git","-C",str(repo),*args],text=True).strip()

def verify_gitlinks(repo):
    assert git(repo,"rev-parse","HEAD")==PINS["EMBEDDED_SIDESTORE_REF"],"Wrong embedded SideStore pin"
    out={}
    for k,path in (("SIDESIGN_REF","Dependencies/SideSign"),
                   ("MINIMUXER_REF","Dependencies/minimuxer")):
        row=git(repo,"ls-tree","HEAD",path).split()
        assert len(row)>=3 and row[0]=="160000" and row[1]=="commit",f"missing gitlink {path}"
        assert row[2]==PINS[k],f"pinned {path} drift"
        assert git(repo/path,"rev-parse","HEAD")==PINS[k],f"checkout {path} mismatch"
        out[k]=row[2]
    return out

def has_install_implementations(repo):
    paths={
        "sidestoreInstall":"SideStore/Core/Operations/PipelineOperations/InstallAppOperation.swift",
        "sidestoreResign":"SideStore/Core/Operations/PipelineOperations/ResignAppOperation.swift",
        "sidestoreRefresh":"SideStore/Core/Operations/PipelineOperations/RefreshAppOperation.swift",
        "sidestoreProfile":"SideStore/Core/Operations/PipelineOperations/FetchProvisioningProfilesOperation.swift",
        "sidestoreSignIn":"SideStore/Core/Operations/StandaloneOperations/SignInOperation.swift",
    }
    missing=[k for k,p in paths.items() if not (repo/p).is_file()]
    assert not missing,f"SideStore install/renew/sign code missing: {missing}"
    return paths

def plist_at(directory):
    p=directory/"Info.plist"
    assert p.is_file(),f"Missing Info.plist: {p}"
    with p.open("rb") as fh:return plistlib.load(fh)

def audit_lc(path):
    assert path.is_dir(),f"Native LiveContainer .app missing: {path}"
    info=plist_at(path)
    binary=path/info["CFBundleExecutable"]
    assert binary.is_file() and binary.stat().st_size>1024,f"Host executable missing: {binary}"
    fmt=subprocess.check_output(["file",str(binary)],text=True)
    assert "Mach-O" in fmt,f"Host not native iOS Mach-O: {fmt}"
    extpaths={s:path/"PlugIns"/(s+".appex") for s in EXTENSIONS}
    for label,ext in extpaths.items():
        assert ext.is_dir(),f"Required app extension missing: {label}"
        p=plist_at(ext)
        assert (ext/p["CFBundleExecutable"]).is_file(),f"Missing executable for {label}"
    support=path/"Frameworks"/"SideStoreSupport.framework"
    assert support.is_dir(),"LiveContainer did not compile built-in SideStoreSupport.framework"
    return {
        "builtHost":True,
        "builtInSideStoreSupport":True,
        "extensionNames":list(extpaths),
        "compiledHostBundle":info.get("CFBundleIdentifier"),
        "sourceInstallPath":"LCAppListView.installIpaFile / LCAppModel.runApp",
        "guestImportAndLaunchVerifiedOnDevice":False
    }

def audit_sidestore(src,ipa):
    implementations=has_install_implementations(src)
    assert ipa.is_file() and ipa.stat().st_size>1000000,"Missing SideStore IPA"
    with zipfile.ZipFile(ipa) as z:
        n=z.namelist()
        apps=sorted(set(p.split("/")[1] for p in n if p.startswith("Payload/") and p.count("/")>=2 and p.endswith("/Info.plist")))
        assert "SideStore.app" in apps, f"SideStore.app not in {apps}"
        host=plistlib.loads(z.read("Payload/SideStore.app/Info.plist"))
        binary=f'Payload/SideStore.app/{host["CFBundleExecutable"]}'
        assert binary in n, f"SideStore executable not packaged: {binary}"
        assert z.getinfo(binary).file_size>1024,"SideStore native executable missing"
    return {
        "builtSideStoreIPA":True,
        "bundle":host["CFBundleIdentifier"],
        "codePaths":implementations,
        "sourceCanAttemptIOSInstall":True,
        "signedIPA":False,
        "appleLoginVerified":False,
        "deviceInstallVerified":False,
        "sevenDayRefreshVerified":False
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--phase",required=True,choices=["pins","livecontainer","sidestore","combined"])
    ap.add_argument("--sidestore-source",type=Path)
    ap.add_argument("--sidestore-ipa",type=Path)
    ap.add_argument("--livecontainer",type=Path)
    ap.add_argument("--combined-ipa",type=Path)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    report={"schema":1,"phase":args.phase,
            "checkedAt":datetime.now(timezone.utc).isoformat(),
            "sourcePins":PINS,
            "realIPhoneTest":False,
            "signingOrAppInstallationCertified":False}
    if args.phase=="pins":
        assert args.sidestore_source
        report["gitlinks"]=verify_gitlinks(args.sidestore_source)
        report["installationCode"]=has_install_implementations(args.sidestore_source)
    elif args.phase=="livecontainer":
        assert args.livecontainer
        report.update(audit_lc(args.livecontainer))
    elif args.phase=="sidestore":
        assert args.sidestore_source and args.sidestore_ipa
        report["gitlinks"]=verify_gitlinks(args.sidestore_source)
        report.update(audit_sidestore(args.sidestore_source,args.sidestore_ipa))
    else:
        assert args.combined_ipa
        with zipfile.ZipFile(args.combined_ipa) as z:
            infolist=z.namelist()
            p="Payload/LiveContainer.app/"
            host=plistlib.loads(z.read(p+"Info.plist"))
            assert host.get("CFBundleIdentifier")==HOST_ID,host.get("CFBundleIdentifier")
            for ext in EXTENSIONS:
                ep=p+"PlugIns/"+ext+".appex/Info.plist"
                d=plistlib.loads(z.read(ep))
                assert d["CFBundleIdentifier"]==HOST_ID+"."+ext,d["CFBundleIdentifier"]
            assert any(x.startswith(p+"Frameworks/SideStoreApp.framework/") for x in infolist)
            assert p+"Frameworks/SideStoreApp.framework/SideStore" in infolist
            report["combinedIPAProduced"]=True
            report["originalHostIdentity"]=HOST_ID
            report["threeExtensionsPreserved"]=True
            report["sideStoreEmbedded"]=True
            report["signingOrAppInstallationCertified"]=False
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("[PASS] Verified source/binary evidence for phase:",args.phase)
    print("[NOTICE] User iPhone installation and app runtime still unverified")
if __name__=="__main__":main()
