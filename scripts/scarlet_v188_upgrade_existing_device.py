#!/usr/bin/env python3
"""Scarlet Crystal V188: cautious upgrade of existing iOS app via paired Wi-Fi/USB.

Never uninstalls the app, changes Apple certificates, or uploads a private key.
Requires an existing installed bundle ID to avoid creating a new app/data container.
Checks on-disk signed IPA, original team/App Group rights, and after-upgrade listing.
"""
import datetime as dt
import hashlib
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import zipfile

APP="com.kdt.livecontainer.P8EZT3U5N4"
TEAM="P8EZT3U5N4"
GROUP="group.com.SideStore.SideStore.P8EZT3U5N4"
NAMES={"Main":APP,"LiveProcess":APP+".LiveProcess",
       "ShareExtension":APP+".ShareExtension",
       "LaunchAppExtension":APP+".LaunchAppExtension"}
ROOT=Path.home()/".local/share/scarlet-crystal/v188-signed"
IPA=ROOT/"Scarlet-Crystal-V188-SIGNED-DEVELOPMENT.ipa"
SHA=ROOT/(IPA.name+".sha256")

class Stop(RuntimeError):pass

def assert_ok(value,msg):
    if not value: raise Stop(msg)

def run(args,timeout=120):
    p=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT,text=True,errors="replace",
                     timeout=timeout)
    if p.returncode:
        raise Stop("COMMAND_FAILED cmd="+str(args[0])+" exit="+str(p.returncode)
                   +" output="+p.stdout[-1800:])
    return p.stdout

def verify_profile(blob, label, expected):
    p=subprocess.run(["openssl","cms","-verify","-inform","DER","-noverify"],
                     input=blob,capture_output=True,timeout=20)
    assert_ok(p.returncode==0,"PROFILE_CMS_INVALID_"+label)
    profile=plistlib.loads(p.stdout)
    e=profile.get("Entitlements",{})
    expiry=profile.get("ExpirationDate")
    if isinstance(expiry,dt.datetime) and expiry.tzinfo is None:
        expiry=expiry.replace(tzinfo=dt.timezone.utc)
    assert_ok(e.get("application-identifier")==TEAM+"."+expected,
              "PROFILE_APP_IDENTIFIER_MISMATCH_"+label)
    assert_ok(GROUP in e.get("com.apple.security.application-groups",[]),
              "PROFILE_ORIGINAL_APP_GROUP_MISSING_"+label)
    assert_ok(expiry and expiry>dt.datetime.now(dt.timezone.utc),
              "PROFILE_EXPIRED_"+label)
    assert_ok(bool(profile.get("ProvisionedDevices")),
              "PROFILE_DEVICE_LIST_EMPTY_"+label)
    print("[PASS] PROFILE_VALID",label,flush=True)

def verify_package():
    assert_ok(IPA.is_file() and IPA.stat().st_size>1000000,"SIGNED_IPA_MISSING")
    assert_ok(SHA.is_file(),"SIGNED_IPA_SHA256_FILE_MISSING")
    expected=SHA.read_text().split()[0].lower()
    current=hashlib.sha256(IPA.read_bytes()).hexdigest()
    assert_ok(expected==current,"SIGNED_IPA_HASH_MISMATCH")
    print("[PASS] SIGNED_IPA_SHA256",current,flush=True)
    with zipfile.ZipFile(IPA) as z:
        assert_ok(z.testzip() is None,"IPA_ARCHIVE_CRC_FAILED")
        members=z.namelist()
        main=[x for x in members if x.startswith("Payload/") and x.endswith(".app/Info.plist") and
              x.count(".app/")==1]
        assert_ok(len(main)==1,"HOST_INFO_COUNT_MISMATCH")
        host=main[0].removesuffix("Info.plist")
        b=plistlib.loads(z.read(main[0]))
        assert_ok(b.get("CFBundleIdentifier")==APP,"HOST_BUNDLE_ID_MISMATCH")
        assert_ok(b.get("CFBundleExecutable"),"HOST_EXECUTABLE_MISSING")
        verify_profile(z.read(host+"embedded.mobileprovision"),"Main",APP)
        plugins=[x for x in members if x.startswith(host+"PlugIns/") and x.endswith(".appex/Info.plist")]
        assert_ok(len(plugins)==3,"EXTENSION_COUNT_MISMATCH")
        ids=set()
        for info_name in plugins:
            d=plistlib.loads(z.read(info_name))
            bundle=d.get("CFBundleIdentifier")
            assert_ok(bundle in set(NAMES.values())-{APP},"UNEXPECTED_EXTENSION_ID")
            name=next(k for k,v in NAMES.items() if v==bundle)
            assert_ok(bundle not in ids,"DUPLICATE_EXTENSION_ID")
            ids.add(bundle)
            verify_profile(z.read(info_name.removesuffix("Info.plist")+"embedded.mobileprovision"),
                           name,bundle)
        assert_ok(ids==set(NAMES.values())-{APP},"THREE_EXTENSION_IDS_INCOMPLETE")
        print("[PASS] FOUR_EXISTING_IDS_AND_PROFILES",flush=True)
        return b.get("CFBundleVersion","")

def devices():
    for t in ("idevice_id","ideviceinstaller"):
        assert_ok(shutil.which(t) is not None,t.upper()+"_NOT_INSTALLED")
    # Prefer already-paired network device for phone-only remote access.
    for scope, flags in (("WiFi",["-n"]),("USB",["-l"])):
        try:
            ids=list(dict.fromkeys(line.strip() for line in run(["idevice_id",*flags],timeout=15).splitlines()
                if line.strip()))
        except Stop:
            ids=[]
        if ids:
            assert_ok(len(ids)==1,"MULTIPLE_DEVICES_CONNECTED")
            print("[PASS] DEVICE_FOUND",scope,flush=True)
            return ids[0], scope=="WiFi"
    raise Stop("NO_PAIRED_DEVICE_OVER_WIFI_OR_USB")

def installed(udid, wifi, version="", before=False):
    args=["ideviceinstaller"]
    if wifi: args.append("-n")
    args+=["-u",udid,"list","--user","-b",APP,"-a","CFBundleIdentifier",
           "-a","CFBundleVersion","-a","CFBundleShortVersionString"]
    output=run(args,timeout=45)
    rows=[x.strip() for x in output.splitlines() if APP in x]
    assert_ok(bool(rows),
              "ORIGINAL_APP_NOT_INSTALLED; DO_NOT_INSTALL_AS_A_SECOND_APP" if before
              else "APP_NOT_FOUND_AFTER_UPGRADE")
    if before:
        print("[PASS] EXISTING_SCARLET_APP_FOUND",flush=True)
    else:
        print("[PASS] EXISTING_SCARLET_APP_PRESENT_AFTER_UPGRADE",flush=True)
        if version and version in output:
            print("[PASS] TARGET_BUILD_VERSION_PRESENT",version,flush=True)
        else:
            print("[CHECK] TARGET_BUILD_VERSION_NOT_EXPOSED_BY_DEVICE_LISTING",flush=True)

def main():
    assert_ok(os.geteuid()!=0,"DO_NOT_RUN_AS_ROOT")
    version=verify_package()
    udid,wifi=devices()
    installed(udid,wifi,before=True)
    args=["ideviceinstaller"]
    if wifi:args.append("-n")
    args+=["-u",udid,"upgrade",IPA]
    print("[UPGRADE] Existing Scarlet Crystal only; no uninstall",flush=True)
    message=run(args,timeout=300)
    print(message[-1800:],flush=True)
    installed(udid,wifi,version=version)
    print("[PASS] V188_DEVICE_UPGRADE_COMMAND_COMPLETED",flush=True)
    print("[NEXT] Open Scarlet Crystal and check app data + Liquid Glass runtime",flush=True)

if __name__=="__main__":
    try:main()
    except Stop as e:
        print("[STOP]",str(e),file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print("[STOP]",type(e).__name__,str(e),file=sys.stderr)
        sys.exit(3)
