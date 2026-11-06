#!/usr/bin/env python3
"""Inject a fresh Scarlet host into pinned upstream LiveContainer, fail closed.

Only new project's UI/core and protected V131 native glass adapter are copied.
Do not apply previous V-series patches or edit LC/SideStore signing assets.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def apply_figma_app_icon(root: Path, engine: Path) -> dict:
    """Build native AppIcon assets from the exact Figma artwork, before actool.

    No host signing assets, app identifiers, guest data or alternate-icon
    catalog entries are removed. macOS sips ships with the Xcode runner.
    """
    source=root/"rebuild/assets/ScarletCrystalAppIcon.figma.png.base64"
    assert source.is_file(), "Figma icon artwork is missing"
    png=base64.b64decode(source.read_text().strip(), validate=True)
    assert png.startswith(b"\\x89PNG\\r\\n\\x1a\\n"), "Invalid PNG signature"
    width,height=struct.unpack(">II",png[16:24])
    assert width>=512 and height>=512 and width==height, (width,height)
    iconset=engine/"Resources/Assets.xcassets/AppIcon.appiconset"
    assert iconset.is_dir(), "Pinned upstream app icon catalog missing"
    manifest=json.loads((iconset/"Contents.json").read_text())
    names=sorted({x["filename"] for x in manifest["images"] if x.get("filename")})
    assert "AppIcon1024.png" in names, "Native primary icon entry missing"
    assert all((iconset/n).is_file() for n in names), "Pinned native icon catalog drift"
    import os
    with tempfile.TemporaryDirectory(prefix="scarlet-figma-icon-") as tmp:
        original=Path(tmp)/"Figma-Icon.png"
        original.write_bytes(png)
        for name in names:
            destination=iconset/name
            subprocess.run(["sips","-s","format","png","-z","1024","1024",
                            str(original),"--out",str(destination)],
                           check=True, stdout=subprocess.DEVNULL)
            output=destination.read_bytes()
            assert output.startswith(b"\\x89PNG\\r\\n\\x1a\\n")
            assert struct.unpack(">II",output[16:24])==(1024,1024)
    return {"sourceFigmaNode":"108:2","inputPixels":[width,height],
            "primaryIcon":"AppIcon1024.png","variants":names,
            "assetSHA256":{n:file_sha(iconset/n) for n in names}}


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
    figma_icon=apply_figma_app_icon(root,engine)
    # Pinned LiveContainer initialization force-unwraps each persisted guest
    # bundle. A damaged/partial historical guest can otherwise terminate the
    # host before any error screen is displayed. Skip that guest only; NEVER
    # delete or rewrite the bundle, container or shared App Group data.
    src=src.replace(original,new)
    boot_anchor="    init() {\\n"
    assert src.count(boot_anchor)==1, "Pinned entry initializer changed"
    src=src.replace(boot_anchor,
        boot_anchor+'        NSLog("[SCARLET_BOOT] phase=app-init-start")\\n')
    guest_anchors={
        'let newApp = LCAppInfo(bundlePath: "\\(LCPath.bundlePath.path)/\\(appDir)")!':
        'guard let newApp = LCAppInfo(bundlePath: "\\(LCPath.bundlePath.path)/\\(appDir)") else {\\n'
        '                    NSLog("[SCARLET_BOOT] invalid-local-guest-skipped")\\n'
        '                    continue\\n'
        '                }',
        'let newApp = LCAppInfo(bundlePath: "\\(LCPath.lcGroupBundlePath.path)/\\(appDir)")!':
        'guard let newApp = LCAppInfo(bundlePath: "\\(LCPath.lcGroupBundlePath.path)/\\(appDir)") else {\\n'
        '                        NSLog("[SCARLET_BOOT] invalid-shared-guest-skipped")\\n'
        '                        continue\\n'
        '                    }'
    }
    for before,after in guest_anchors.items():
        assert src.count(before)==1, f"Pinned guest initializer changed: {before}"
        src=src.replace(before,after)
    entry.write_text(src)

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
        "invalidPersistedGuestSkippedWithoutMutation":True,
        "hostBootPhaseLoggingInjected":True,
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

        "customAppIcon":figma_icon,
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
    print("[PASS] New Figma Scarlet icon compiled into AppIcon.appiconset source; Xcode archive pending")
    print("[BLOCK] Await actual Xcode archive and iPhone runtime validation")
if __name__=="__main__":main()
