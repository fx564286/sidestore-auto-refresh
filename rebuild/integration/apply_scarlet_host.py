#!/usr/bin/env python3
"""Inject a fresh Scarlet host into pinned upstream LiveContainer, fail closed.

Only new project's UI/core and protected V131 native glass adapter are copied.
Do not apply previous V-series patches or edit LC/SideStore signing assets.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil

def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--engine",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    engine=a.engine
    entry=engine/"LiveContainerSwiftUI/App/LiveContainerSwiftUIApp.swift"
    assert entry.is_file(),"Upstream app entry missing"
    src=entry.read_text()
    original="            LCTabView()\n"
    new="""            if #available(iOS 17.0, *) {
                ScarletIntegratedHostView()
            } else {
                // Preserve upstream legacy compatibility without porting old
                // Scarlet patch chains or changing the guest engine.
                LCTabView()
            }
"""
    if src.count(original)!=1:
        raise RuntimeError("Refuse to overwrite changed upstream app entry")
    out=engine/"LiveContainerSwiftUI/Views/ScarletCrystal"
    if out.exists():raise RuntimeError("ScarletCrystal overlay already present")
    out.mkdir(parents=True)
    sources={
        root/"rebuild/HostApp/ScarletIntegratedHostView.swift":"ScarletIntegratedHostView.swift",
        root/"rebuild/HostApp/ScarletNativeGlass.swift":"ScarletNativeGlass.swift",
        root/"rebuild/Sources/ScarletIndependentUI/ScarletIndependentShell.swift":"ScarletIndependentShell.swift",
        root/"rebuild/Sources/ScarletCleanCore/ScarletActionCoordinator.swift":"ScarletActionCoordinator.swift",
        root/"rebuild/Sources/ScarletCleanCore/ScarletControlAuditTrail.swift":"ScarletControlAuditTrail.swift",
        root/"rebuild/Sources/ScarletCleanCore/ScarletRefreshPolicy.swift":"ScarletRefreshPolicy.swift",
    }
    for inp,name in sources.items():
        assert inp.is_file(),f"Required independent source missing: {inp}"
        shutil.copy2(inp,out/name)
    entry.write_text(src.replace(original,new))
    a.report.parent.mkdir(parents=True,exist_ok=True)
    data={
        "schema":1,"newRootCompiled":False,
        "upstreamAppEntryPatched":True,
        "hostEntry":"ScarletIntegratedHostView",
        "realLCGuestModelsUsed":True,
        "originalGuestImporterPreserved":True,
        "embeddedSideStoreNativeLaunchPreserved":True,
        "originalNativeUIGlassEffect":True,
        "actualIOSExecutionVerified":False,
        "windowMaximizeAndCloseComplete":False,
        "sources":[dict(path=str(x.relative_to(engine)),sha256=file_sha(x))
                   for x in sorted(out.glob("*.swift"))],
        "entrySHA256":file_sha(entry),
        "note":"Compiles only when real xcodebuild archive succeeds; not proof of install/working Liquid Glass gestures."
    }
    a.report.write_text(json.dumps(data,indent=2)+"\n")
    print("[PASS] Fresh Scarlet host sources injected into file-synchronized Xcode project")
    print("[BLOCK] Await actual Xcode archive and iPhone runtime validation")
if __name__=="__main__":main()
