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
    new="""            Group {
                if #available(iOS 17.0, *) {
                    ScarletIntegratedHostView()
                } else {
                    // Preserve original fallback on older supported iOS.
                    LCTabView()
                }
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
        root/"rebuild/HostApp/ScarletGuestSwitcherOverlay.swift":"ScarletGuestSwitcherOverlay.swift",
        root/"rebuild/HostApp/ScarletAppleIDLoginSheet.swift":"ScarletAppleIDLoginSheet.swift",
        root/"rebuild/Sources/ScarletIndependentUI/ScarletIndependentShell.swift":"ScarletIndependentShell.swift",
        root/"rebuild/Sources/ScarletCleanCore/ScarletActionCoordinator.swift":"ScarletActionCoordinator.swift",
        root/"rebuild/Sources/ScarletCleanCore/ScarletControlAuditTrail.swift":"ScarletControlAuditTrail.swift",
        root/"rebuild/Sources/ScarletCleanCore/ScarletRefreshPolicy.swift":"ScarletRefreshPolicy.swift",
    }
    for inp,name in sources.items():
        assert inp.is_file(),f"Required independent source missing: {inp}"
        shutil.copy2(inp,out/name)
    entry.write_text(src.replace(original,new))

    # Mount the sole circular control on an actual running guest scene.  Never
    # place it over the independent host container tabs.  Refuse unknown pins.
    guest_window=engine/"MultitaskSupport/MultitaskAppWindow.swift"
    assert guest_window.is_file(),"Pinned LiveContainer guest window file missing"
    guest_src=guest_window.read_text()
    anchors={
        "        return AppSceneViewController(bundleId: bundleId, dataUUID: dataUUID, delegate: context.coordinator)\n":
        "        guard let controller = AppSceneViewController(bundleId: bundleId, dataUUID: dataUUID, delegate: context.coordinator) else {\n"
        "            return UIViewController()\n"
        "        }\n"
        "        ScarletGuestSceneRegistry.register(controller, dataUUID: dataUUID)\n"
        "        return controller\n",
        "            if !show {\n                vc.terminate()\n":
        "            if !show {\n                ScarletGuestSceneRegistry.unregister(dataUUID)\n                vc.terminate()\n",
        "                .background(.black)\n                .frame(maxWidth: .infinity, maxHeight: .infinity)\n":
        "                .background(.black)\n"
        "                .frame(maxWidth: .infinity, maxHeight: .infinity)\n"
        "                .overlay(alignment: .bottomLeading) {\n"
        "                    if #available(iOS 17.0, *) {\n"
        "                        ScarletGuestSwitcherOverlay(dataUUID: appInfo.dataUUID, displayName: appInfo.displayName)\n"
        "                    }\n"
        "                }\n"
        "                .onDisappear { ScarletGuestSceneRegistry.unregister(appInfo.dataUUID) }\n"
    }
    for before,after in anchors.items():
        if guest_src.count(before)!=1:
            raise RuntimeError(f"Unexpected pinned guest scene layout; anchor count={guest_src.count(before)}: {before!r}")
        guest_src=guest_src.replace(before,after)
    guest_window.write_text(guest_src)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    data={
        "schema":1,"newRootCompiled":False,
        "upstreamAppEntryPatched":True,
        "hostEntry":"ScarletIntegratedHostView",
        "realLCGuestModelsUsed":True,
        "originalGuestImporterPreserved":True,
        "embeddedSideStoreNativeLaunchPreserved":True,
        "originalNativeUIGlassEffect":True,
        "upstreamLiveContainerSourceUntouched":False,
        "upstreamLiveContainerModifiedTrackedPaths":[
            "LiveContainerSwiftUI/App/LiveContainerSwiftUIApp.swift",
            "MultitaskSupport/MultitaskAppWindow.swift"
        ],

        "guestOnlySwitcherSourceInjected":True,
        "guestSnapshotCaptureSourceInjected":True,
        "guestRuntimeCaptureDeviceVerified":False,
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
