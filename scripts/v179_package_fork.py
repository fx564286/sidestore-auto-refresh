#!/usr/bin/env python3
"""Package a *real*, unsigned Scarlet Crystal derivative from both built parents.

Uses LiveContainer's actual upstream combined packaging script and locally
compiled SideStore, not a downloaded prebuilt SideStore or placeholder IPA.
This integration candidate is NOT evidence that historical custom UI overlays
all survived a source-forward-port; only the linked artifacts are verified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import zipfile

from package_livecontainer_combined import adapt

EXPECTED_HOST_ID = "com.kdt.livecontainer"
EXPECTED_DISPLAY_NAME = "Scarlet Crystal"
EXPECTED_VERSION = "V179"
MACHO = (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca")

def stamp(host):
    info_path = host / "Info.plist"
    value = plistlib.loads(info_path.read_bytes())
    bundle_id = value.get("CFBundleIdentifier", "")
    if not bundle_id.startswith(EXPECTED_HOST_ID):
        raise ValueError(f"unexpected host identity: {bundle_id}")
    value["CFBundleDisplayName"] = EXPECTED_DISPLAY_NAME
    value["CFBundleName"] = EXPECTED_DISPLAY_NAME
    value["ScarletBuildLabel"] = EXPECTED_VERSION
    value["ScarletParentIntegration"] = "LiveContainer/main+LiveContainer/SideStore/LiveContainerSupport"
    info_path.write_bytes(plistlib.dumps(value, sort_keys=False))

def check(ipa, side, parent_shas):
    result = {"schema": 1, "build": EXPECTED_VERSION, "ipa": str(ipa),
              "sha256": hashlib.sha256(ipa.read_bytes()).hexdigest(),
              "parent_shas": parent_shas,
              "custom_ui_runtime_verified": False,
              "device_remote_pairing_verified": False}
    with zipfile.ZipFile(ipa) as archive:
        names = set(archive.namelist())
        root = "Payload/LiveContainer.app/"
        info = plistlib.loads(archive.read(root + "Info.plist"))
        result["host_bundle_id"] = info.get("CFBundleIdentifier")
        result["display_name"] = info.get("CFBundleDisplayName")
        if result["display_name"] != EXPECTED_DISPLAY_NAME:
            raise ValueError("Scarlet Crystal branding missing")
        if not str(result["host_bundle_id"]).startswith(EXPECTED_HOST_ID):
            raise ValueError("unexpected packaged host identifier")
        if info.get("ScarletBuildLabel") != EXPECTED_VERSION:
            raise ValueError("source build marker missing")
        expected_side = root + "Frameworks/SideStoreApp.framework/SideStore"
        if expected_side not in names:
            raise ValueError("embedded local SideStore executable missing")
        if archive.read(expected_side)[:4] not in MACHO:
            raise ValueError("embedded SideStore is not a Mach-O executable")
        executable = info.get("CFBundleExecutable")
        if not executable or root + executable not in names:
            raise ValueError("host executable missing")
        if archive.read(root + executable)[:4] not in MACHO:
            raise ValueError("host is not a Mach-O executable")
        extensions = []
        for name in names:
            if name.startswith(root + "PlugIns/") and name.endswith(".appex/Info.plist"):
                extensions.append(name.split("/")[3])
        extensions = sorted(extensions)
        result["extensions"] = extensions
        if "LiveProcess.appex" not in extensions:
            raise ValueError("LiveProcess guest runtime extension missing")
        if "LiveWidgetExtension.appex" in extensions:
            raise ValueError("retired extra widget was reintroduced")
        if not any(name.startswith(root+"Frameworks/SideStoreSupport.framework/")
                   for name in names):
            raise ValueError("host SideStore support framework missing")
    compiled_side = side / "SideStore"
    if not compiled_side.is_file():
        raise ValueError("locally compiled SideStore source product not found")
    result["local_side_sha256"] = hashlib.sha256(compiled_side.read_bytes()).hexdigest()
    result["verified"] = True
    return result

def package(root, host, side, output, parent_shas):
    for target in (host, side):
        if not (target / "Info.plist").is_file():
            raise ValueError(f"missing compiled parent app: {target}")
    if any((root / p).exists() for p in ("Payload", "tmp", "patched-side")):
        raise ValueError("staging is not clean; refusing mixed-parent IPA")
    stage = root / "combined.xcarchive/Products/Applications"
    stage.mkdir(parents=True)
    shutil.copytree(host, stage / "LiveContainer.app", symlinks=True)
    stamp(stage / "LiveContainer.app")
    side_stage = root / "patched-side/Payload"
    side_stage.mkdir(parents=True)
    shutil.copytree(side, side_stage / "SideStore.app", symlinks=True)
    side_zip = root / "PatchedSideStore.ipa"
    subprocess.run(["zip", "-qry", str(side_zip), "Payload"], cwd=side_stage.parent, check=True)
    upstream = (root / ".github/build_github.sh").read_text()
    transformed = adapt(upstream)
    script = root / "scarlet-v179-combined-build.sh"
    script.write_text(transformed)
    env = dict(os.environ, archive_path="combined", scheme="LiveContainer",
        PATCHED_SIDESTORE_IPA=str(side_zip),
        COMBINED_PACKAGER=str((Path(__file__).resolve().parent /
                               "package_livecontainer_combined.py").resolve()),
        V67_PATCH=str((Path(__file__).resolve().parent / "patch_v67_three_ids.py").resolve()))
    subprocess.run(["bash", str(script)], cwd=root, env=env, check=True)
    combined = root / "LiveContainer+SideStore.ipa"
    if not combined.is_file():
        raise ValueError("upstream combined packaging created no IPA")
    result = check(combined, side, parent_shas)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(combined, output)
    output.with_suffix(".json").write_text(json.dumps(result, indent=2)+"\n")
    print("[PASS] real Scarlet Crystal fork IPA compiled from both parent sources")
    print(json.dumps(result, indent=2))

def main():
    parser = argparse.ArgumentParser()
    for name in ("root", "host", "side", "output", "pin-file"):
        parser.add_argument("--"+name, type=Path, required=True)
    args = parser.parse_args()
    parent_shas = json.loads(args.pin_file.read_text())
    package(args.root.resolve(), args.host.resolve(), args.side.resolve(),
            args.output.resolve(), parent_shas)

if __name__ == "__main__":
    main()
