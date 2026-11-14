#!/usr/bin/env python3
"""Rebase an UNSIGNED Scarlet host IPA so SideInstaller signs to the EXISTING app ID.

SideInstaller's vendored isideload always signs the main IPA as
    <unsigned main CFBundleIdentifier> + "." + <Apple Team ID>
and transforms extension IDs by replacing that main prefix with the signed one.
Scarlet source/CI compiles for the established installed ID, but its distributed
SideInstaller input must omit the final team suffix to avoid a second app ID.

Only edit plist bundle identifiers in the unsigned Release asset. Never change
the compiled executable, guest data, Apple signing assets, or installed device.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import plistlib
import tempfile
import zipfile

EXTENSIONS=("LiveProcess","ShareExtension","LaunchAppExtension")
HOST_APP="Payload/LiveContainer.app"

def _plist(data: bytes, new_id: str) -> bytes:
    info=plistlib.loads(data)
    info["CFBundleIdentifier"]=new_id
    fmt=plistlib.FMT_BINARY if data.startswith(b"bplist00") else plistlib.FMT_XML
    return plistlib.dumps(info,fmt=fmt,sort_keys=False)

def rebase_unsigned_ipa(source: Path, dest: Path, installed_host_id: str,
                        team_id: str, expected_build: str) -> None:
    if not team_id or not installed_host_id.endswith("."+team_id):
        raise ValueError("Installed host ID must end with the chosen Apple team ID")
    raw_host_id=installed_host_id[:-(len(team_id)+1)]
    if raw_host_id.count(".")<2 or not raw_host_id.startswith("com."):
        raise ValueError("Unsafe unsigned host identity")
    if source.resolve()==dest.resolve():
        raise ValueError("Never modify original unsigned IPA in place")
    replacements={
        HOST_APP+"/Info.plist":(installed_host_id,raw_host_id)
    }
    for ext in EXTENSIONS:
        name=f"{HOST_APP}/PlugIns/{ext}.appex/Info.plist"
        replacements[name]=(installed_host_id+"."+ext,raw_host_id+"."+ext)
    dest.parent.mkdir(parents=True,exist_ok=True)
    tmp_path=None
    try:
        with tempfile.NamedTemporaryFile(dir=dest.parent,
                                         prefix=".scarlet-sideinstaller-",
                                         suffix=".ipa",delete=False) as f:
            tmp_path=Path(f.name)
        with zipfile.ZipFile(source,"r") as src, zipfile.ZipFile(tmp_path,"w") as out:
            names=set(src.namelist())
            if len(names)!=len(src.namelist()):
                raise ValueError("IPA contains duplicate ZIP names")
            missing=set(replacements)-names
            if missing:
                raise ValueError("Required app / extension plist missing: "+",".join(sorted(missing)))
            for item in src.infolist():
                data=src.read(item)
                if item.filename in replacements:
                    old,new=replacements[item.filename]
                    info=plistlib.loads(data)
                    if info.get("CFBundleIdentifier")!=old:
                        raise ValueError(f"Unexpected current ID in {item.filename}")
                    if item.filename==HOST_APP+"/Info.plist":
                        if info.get("CFBundleVersion")!=expected_build:
                            raise ValueError(f"Unexpected host build: {info.get('CFBundleVersion')}")
                    data=_plist(data,new)
                # ZipInfo retains UNIX executable/symlink metadata, compression
                # method, timestamps and archive path; only four plists change.
                out.writestr(item,data)
        with zipfile.ZipFile(tmp_path) as check:
            if check.testzip() is not None:
                raise ValueError("rebased IPA failed ZIP CRC validation")
            for name,(old,new) in replacements.items():
                got=plistlib.loads(check.read(name))["CFBundleIdentifier"]
                if got!=new:
                    raise ValueError(f"Rebase readback failed for {name}")
                predicted_signed=got+"."+team_id if name==HOST_APP+"/Info.plist" else (
                    installed_host_id+got[len(raw_host_id):])
                if predicted_signed!=old:
                    raise ValueError(f"SideInstaller signing would produce wrong ID: {name}")
        os.replace(tmp_path,dest)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--installed-host-id",required=True)
    p.add_argument("--team-id",required=True)
    p.add_argument("--build",required=True)
    args=p.parse_args()
    rebase_unsigned_ipa(args.source,args.output,args.installed_host_id,
                        args.team_id,args.build)
    print("[SIDEINSTALLER-COMPAT] source host ID rebased to match expected installed ID after signing",flush=True)
    print("[PASS] app + 3 extension bundle IDs and post-sign identity predicted, CRC valid",flush=True)

if __name__=="__main__":
    main()
