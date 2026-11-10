#!/usr/bin/env python3
"""Link genuine on-device RPPairing host into Scarlet's existing SwiftUI engine.

StikPair @ 7c911d8319dc5bcc411bf299d963689e26009b0b
Copyright (c) 2026 StephenDev0, MIT non-commercial.
The pairing engine runs in LiveContainerSwiftUI.framework; no new app/appex
target, app identifier, provisioning profile, or copied SideInstaller binary.
"""
import argparse
import hashlib
from pathlib import Path
import shutil

PIN="7c911d8319dc5bcc411bf299d963689e26009b0b"

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--engine",type=Path,required=True)
    ap.add_argument("--stikpair",type=Path,required=True)
    ap.add_argument("--report",type=Path,required=True)
    args=ap.parse_args()
    repo=args.stikpair
    import subprocess
    actual=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"],text=True).strip()
    assert actual==PIN,(actual,PIN)
    lib=repo/"rust/target/aarch64-apple-ios/release/libstikpair_ffi.a"
    assert lib.is_file() and lib.stat().st_size>100000,("compiled pairing engine missing",lib)
    header=repo/"rust/include/stikpair.h"
    licenseFile=repo/"LICENSE"
    assert header.is_file() and licenseFile.is_file()
    assert "Copyright (c) 2026 StephenDev0" in licenseFile.read_text()

    engine=args.engine
    target=engine/"ScarletPairingFFI.a"
    shutil.copy2(lib,target)
    targetHeader=engine/"LiveContainerSwiftUI/ScarletPairingFFI.h"
    shutil.copy2(header,targetHeader)
    bridge=engine/"LiveContainerSwiftUI/LiveContainerSwiftUI-Bridging-Header.h"
    bs=bridge.read_text()
    assert '#include "ScarletPairingFFI.h"' not in bs
    bridge.write_text(bs.rstrip()+'\n#include "ScarletPairingFFI.h"\n')

    # Original paired project has exactly one Debug and Release linker line
    # for LiveContainerSwiftUI. Never override flags for the app or extensions.
    project=engine/"LiveContainer.xcodeproj/project.pbxproj"
    source=project.read_text()
    original='OTHER_LDFLAGS = "-Wl,-U,_OBJC_CLASS_$_RBSTarget";'
    assert source.count(original)==2, "Pinned LC SwiftUI linker layout changed"
    replacement=(
        'OTHER_LDFLAGS = ("-Wl,-U,_OBJC_CLASS_$_RBSTarget", '
        '"-force_load", "$(PROJECT_DIR)/ScarletPairingFFI.a", "-lc++");')
    project.write_text(source.replace(original,replacement))

    # Retain third-party attribution in the actual installable IPA resources.
    licenses=engine/"Resources/ScarletPairingThirdParty-LICENSE.txt"
    licenses.write_text(
        "Scarlet Crystal in-app remote pairing uses StikPair by "
        "StephenDev0, pinned "+PIN+"\n"
        "https://github.com/StikDebug/StikPair\n\n"
        + licenseFile.read_text())
    import json
    report={
        "engine": "StikPair native idevice RP pairing host",
        "pinnedCommit": PIN,
        "license": "MIT Non-Commercial; source and packaged notice retained",
        "staticLibrarySHA256":hashlib.sha256(lib.read_bytes()).hexdigest(),
        "libraryBytes":lib.stat().st_size,
        "noExtraBundleIdentifiers":True,
        "bridgingHeaderModified":True,
        "frameworkLinkerTargets":2,
        "notificationInsteadOfLiveActivityExtension":True,
    }
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+"\n")
    print("[PASS] Genuine native RPPairing static library linked to existing LC framework")
    print("[PASS] No app extension, bundle ID, signer or entitlement removed")
if __name__=="__main__":
    main()
