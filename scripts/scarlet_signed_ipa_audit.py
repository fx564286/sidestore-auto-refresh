#!/usr/bin/env python3
"""Read-only pre-install audit for the four Scarlet Crystal iOS signed bundles.

No Apple login, signing, entitlement rewriting, device installation or deletion.
An accepted audit is NOT an iOS installation or App Group runtime test.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import re
import ssl
import subprocess
import sys
import tempfile
import zipfile

import scarlet_entitlement_recovery as core

ROOT="Payload/LiveContainer.app/"
APPEX=re.compile(r"Payload/LiveContainer[.]app/PlugIns/[^/]+[.]appex/Info[.]plist")


def match_declared_entitlements(bundle, signed, profile, original=None):
    expected=core.TEAM+"."+bundle
    if signed.get("application-identifier")!=expected:
        raise core.Halt("signed application identifier mismatch for "+bundle)
    if signed.get("com.apple.developer.team-identifier")!=core.TEAM:
        raise core.Halt("signed Apple Team mismatch for "+bundle)
    if bundle==core.MAIN:
        if original is None:
            raise core.Halt("historic host entitlements required")
        core.historical_host(original)
        for key in (core.KEYCHAINS, core.GROUPS):
            actual, expected = signed.get(key), original.get(key)
            if (not isinstance(actual, list)
                    or len(actual) != len(expected)
                    or set(actual) != set(expected)):
                raise core.Halt("host entitlement changed from historical baseline: "+key)
        if signed.get(core.MEMORY) is not True:
            raise core.Halt("host memory grant changed from historical baseline")
    for key in (core.KEYCHAINS,core.GROUPS):
        actual=signed.get(key,[])
        if not isinstance(actual,list):
            raise core.Halt("invalid signed entitlement: "+key)
        allowed=profile.get(key,[])
        if actual and (not isinstance(allowed,list) or
                       not all(core.grants(value,allowed) for value in actual)):
            raise core.Halt("signed entitlement not authorized by Apple profile: "+bundle+"/"+key)
    if signed.get(core.MEMORY,False) is True and profile.get(core.MEMORY) is not True:
        raise core.Halt("signed memory capability not authorized for "+bundle)
    if "get-task-allow" in signed and signed["get-task-allow"]!=profile.get("get-task-allow"):
        raise core.Halt("signed get-task-allow does not match profile: "+bundle)


def verify_profile(blob, bundle, certificate_der, udid):
    from subprocess import run, PIPE
    p=run(["openssl","cms","-verify","-inform","DER","-noverify"],
          input=blob,stdout=PIPE,stderr=PIPE,timeout=15)
    if p.returncode:
        raise core.Halt("embedded provisioning CMS integrity failed: "+bundle)
    data=core.decode_plist(p.stdout)
    app, rights=core.profile_info(data)
    if app!=bundle:
        raise core.Halt("embedded provisioning profile belongs to another bundle: "+bundle)
    if udid not in data.get("ProvisionedDevices",[]):
        raise core.Halt("device UDID not present in embedded profile: "+bundle)
    if not any(bytes(cert)==certificate_der for cert in data.get("DeveloperCertificates",[])):
        raise core.Halt("signing certificate is not authorized in embedded profile: "+bundle)
    return rights


def ldid_entitlements(blob):
    with tempfile.TemporaryDirectory(prefix="scarlet-bundle-audit-") as temp:
        file=Path(temp)/"bundle-macho"
        if len(blob)>200*1024*1024:
            raise core.Halt("Mach-O exceeds audit limit")
        file.write_bytes(blob)
        r=subprocess.run(["ldid","-e",str(file)],capture_output=True,timeout=15)
        if r.returncode or not r.stdout:
            raise core.Halt("missing signed Mach-O entitlements")
        return core.decode_plist(r.stdout)


def audit(ipa, baseline, cert_der, udid):
    original=core.historical_host(core.decode_plist(Path(baseline).read_bytes()))
    with zipfile.ZipFile(ipa) as archive:
        if archive.testzip() is not None:
            raise core.Halt("signed IPA ZIP integrity failed")
        infos=[ROOT+"Info.plist"]+[n for n in archive.namelist() if APPEX.fullmatch(n)]
        if len(infos)!=4:
            raise core.Halt("expected exactly one host and three extensions")
        found=set()
        for info_path in infos:
            info=plistlib.loads(archive.read(info_path))
            bundle=info.get("CFBundleIdentifier")
            if bundle not in core.BUNDLES or bundle in found:
                raise core.Halt("duplicate or unknown signed bundle")
            found.add(bundle)
            executable=info.get("CFBundleExecutable")
            if not isinstance(executable,str) or not executable or "/" in executable or "\\" in executable:
                raise core.Halt("invalid bundle executable name")
            folder=info_path.removesuffix("Info.plist")
            executable_path=folder+executable
            emb=folder+"embedded.mobileprovision"
            if executable_path not in archive.namelist() or emb not in archive.namelist():
                raise core.Halt("signed executable or profile absent: "+bundle)
            profile=verify_profile(archive.read(emb),bundle,cert_der,udid)
            signed=ldid_entitlements(archive.read(executable_path))
            match_declared_entitlements(bundle,signed,profile,original if bundle==core.MAIN else None)
        if found!=core.BUNDLES:
            raise core.Halt("missing required signed bundle")
    return sorted(found)


def identity_from_cached_renewal(home):
    state=core.latest_profile_dir(home)
    manifest=state/"manifest.json"
    cert=state/"cert.pem"
    if not manifest.is_file() or not cert.is_file():
        raise core.Halt("cached profile identity manifest or cert missing")
    record=json.loads(manifest.read_text())
    if record.get("team")!=core.TEAM or set(record.get("bundle_ids",[]))!=core.BUNDLES:
        raise core.Halt("cached renewal identity does not match all four bundles")
    udid=record.get("udid")
    if not isinstance(udid,str) or not udid:
        raise core.Halt("cached provisioning device ID missing")
    p=subprocess.run(["openssl","x509","-in",str(cert),"-outform","DER"],
                     capture_output=True,timeout=15)
    if p.returncode or not p.stdout:
        raise core.Halt("cached signing certificate is unreadable")
    der=p.stdout
    if hashlib.sha256(der).hexdigest()!=record.get("certificate_sha256"):
        raise core.Halt("cached certificate digest mismatch")
    return der,udid


def main(argv):
    ap=argparse.ArgumentParser(description="Strict four-bundle signed IPA rights audit: no install")
    ap.add_argument("ipa",type=Path,help="local signed Scarlet IPA")
    ap.add_argument("--historical-entitlements",type=Path,
                    default=Path.home()/"다운로드/NRG-IPA/SCARLET-CRYSTAL-251-MEMORY-RESTORE-20261022/entitlements.xml")
    opts=ap.parse_args(argv)
    der,udid=identity_from_cached_renewal(Path.home())
    result=audit(opts.ipa.expanduser(),opts.historical_entitlements.expanduser(),der,udid)
    print(f"[PASS] Signed bundles verified: {len(result)}")
    print("[PASS] Host Keychain, App Group and memory entitlements match historical baseline")
    print("[NOTE] iPhone runtime, cryptographic Mach-O seal, Safari OTA and installed app parity still require separate tests")
    return 0


if __name__=="__main__":
    try: raise SystemExit(main(sys.argv[1:]))
    except (core.Halt,FileNotFoundError,zipfile.BadZipFile,subprocess.TimeoutExpired) as exc:
        print("[STOP]",exc,file=sys.stderr)
        raise SystemExit(2)
