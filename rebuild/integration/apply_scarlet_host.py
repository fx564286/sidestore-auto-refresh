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
    assert png.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG signature"
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
            assert output.startswith(b"\x89PNG\r\n\x1a\n")
            assert struct.unpack(">II",output[16:24])==(1024,1024)
    return {"sourceFigmaNode":"108:2","inputPixels":[width,height],
            "primaryIcon":"AppIcon1024.png","variants":names,
            "assetSHA256":{n:file_sha(iconset/n) for n in names}}


def hide_embedded_sidestore_guest_navigation(engine: Path) -> dict:
    """Retain SideStore/SideSign engines, remove only its *guest UI* shortcuts.

    The user wants the original LiveContainer app manager with IPA/URL import,
    but not a second SideStore application window. Keep SideStoreSupport,
    LiveProcess and refresh IPC untouched. Exact source anchors refuse drift.
    """
    view=engine/"LiveContainerSwiftUI/Views/AppList/LCAppListView.swift"
    assert view.is_file(), "Pinned native LiveContainer app manager missing"
    source=view.read_text()

    # Native toolbar: the first leading item is the real IPA/URL add menu.
    # Only the SECOND item launches the bundled SideStore guest application.
    toolbar_start="""                ToolbarItem(placement: .topBarLeading) {
                    if(UserDefaults.sideStoreExist()) {
"""
    next_item="""                ToolbarItem(placement: .topBarTrailing) {
"""
    assert source.count(toolbar_start)==1, "Native SideStore guest toolbar changed"
    prefix, remainder=source.split(toolbar_start,1)
    assert remainder.count(next_item)>=1, "Native guest toolbar end changed"
    removed, rest=remainder.split(next_item,1)
    for expected in ("LCUtils.openSideStore(delegate: self)",
                     "BuiltInSideStoreAppInfo.shared.iconIsDarkIcon"):
        assert removed.count(expected)==1, f"Native SideStore guest button changed: {expected}"
    source=prefix+next_item+rest
    assert 'Button("lc.appList.installFromIpa".loc' in source
    assert 'Button("lc.appList.installFromUrl".loc' in source

    # No hidden secondary path via the guest launch ID or SideStore URL.
    builtin="""        if appFound == nil && bundleId == "builtinSideStore" {
            appFound = LCAppModel(appInfo: BuiltInSideStoreAppInfo.shared)
        }
"""
    assert source.count(builtin)==1, "Pinned builtin SideStore guest launch changed"
    source=source.replace(builtin,"")

    deeplink="""        if url.scheme == "sidestore" && UserDefaults.sideStoreExist() {
            UserDefaults.standard.setValue(url.absoluteString, forKey: "launchAppUrlScheme")
            LCUtils.openSideStore(delegate: self)
            return
        }
"""
    assert source.count(deeplink)==1, "Pinned SideStore deeplink route changed"
    source=source.replace(deeplink,
        '        if url.scheme == "sidestore" {\n'
        '            NSLog("[SCARLET_ROUTE] SideStore guest UI disabled; engine retained")\n'
        '            return\n'
        '        }\n')
    assert "LCUtils.openSideStore(" not in source
    assert "BuiltInSideStoreAppInfo.shared" not in source
    view.write_text(source)
    return {"appManager":"LCAppListView",
            "nativeIPAImportPreserved":True,
            "nativeURLImportPreserved":True,
            "embeddedSideStoreGuestNavigationRemoved":True,
            "embeddedSideStoreEnginePreserved":True,
            "changedFile":str(view.relative_to(engine)),
            "patchedFileSHA256":file_sha(view)}


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
    boot_anchor="    init() {\n"
    assert src.count(boot_anchor)==1, "Pinned entry initializer changed"
    src=src.replace(boot_anchor,
        boot_anchor+'        NSLog("[SCARLET_BOOT] phase=app-init-start")\n')
    guest_anchors={
        'let newApp = LCAppInfo(bundlePath: "\(LCPath.bundlePath.path)/\(appDir)")!':
        'guard let newApp = LCAppInfo(bundlePath: "\(LCPath.bundlePath.path)/\(appDir)") else {\n'
        '                    NSLog("[SCARLET_BOOT] invalid-local-guest-skipped")\n'
        '                    continue\n'
        '                }',
        'let newApp = LCAppInfo(bundlePath: "\(LCPath.lcGroupBundlePath.path)/\(appDir)")!':
        'guard let newApp = LCAppInfo(bundlePath: "\(LCPath.lcGroupBundlePath.path)/\(appDir)") else {\n'
        '                        NSLog("[SCARLET_BOOT] invalid-shared-guest-skipped")\n'
        '                        continue\n'
        '                    }'
    }
    for before,after in guest_anchors.items():
        assert src.count(before)==1, f"Pinned guest initializer changed: {before}"
        src=src.replace(before,after)
    url_schemes_anchor="tempURLSchemes?.formUnion(newApp.urlSchemes() as! [String])"
    assert src.count(url_schemes_anchor)==2, "Pinned URL scheme loader changed"
    src=src.replace(url_schemes_anchor,
        'if let schemes = newApp.urlSchemes() as? [String] {\n'
        '                        tempURLSchemes?.formUnion(schemes)\n'
        '                    }')
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

    # The 2026-11-06 on-device crashes (four identical SIGTRAP/BRK #1 in
    # LiveContainerSwiftUI UUID A87CD742-820E-3F50-A48B-481388DCF3B1,
    # PC imageOffset 0x22ACC) identify the pinned dock's force unwrap:
    # keyWindow!.rootViewController!.view.subviews.first!
    # The fresh SwiftUI shell requests MultitaskDockManager.shared before
    # UIWindow has attached its root hierarchy. Preserve the actual dock
    # engine and user windows; defer its attachment until a view exists.
    dock_src_file=engine/"MultitaskSupport/MultitaskDockView.swift"
    assert dock_src_file.is_file(), "Pinned LiveContainer dock source missing"
    dock_source=dock_src_file.read_text()
    unsafe_init="""    override init() {
        super.init()
        keyWindow!.rootViewController!.view.subviews.first!.addSubview(self.windowHostingView)
        setupDockView()
"""
    safe_init="""    // Scarlet: app startup may evaluate the dock before UIKit creates its
    // first key window. Mount the same native host after the scene is ready.
    public func scarletEnsureWindowHost() {
        guard let rootView = keyWindow?.rootViewController?.view else { return }
        let target = rootView.subviews.first(where: { $0 !== windowHostingView }) ?? rootView
        if windowHostingView.superview !== target {
            windowHostingView.removeFromSuperview()
            target.addSubview(windowHostingView)
        }
    }

    @objc private func scarletWindowBecameVisible(_ notification: Notification) {
        DispatchQueue.main.async { [weak self] in
            self?.scarletEnsureWindowHost()
        }
    }

    override init() {
        super.init()
        scarletEnsureWindowHost()
        NotificationCenter.default.addObserver(self,
            selector: #selector(scarletWindowBecameVisible(_:)),
            name: UIWindow.didBecomeVisibleNotification,
            object: nil)
        setupDockView()
"""
    assert dock_source.count(unsafe_init)==1, "Pinned dock startup layout changed"
    dock_source=dock_source.replace(unsafe_init,safe_init)
    assert "keyWindow!.rootViewController!.view.subviews.first!" not in dock_source, "Unsafe force unwrap retained"
    dock_src_file.write_text(dock_source)
    guest_manager=hide_embedded_sidestore_guest_navigation(engine)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    data={
        "schema":1,"newRootCompiled":False,
        "upstreamAppEntryPatched":True,
        "invalidPersistedGuestSkippedWithoutMutation":True,
        "hostBootPhaseLoggingInjected":True,
        "onDeviceSigtrapDockForceUnwrapGuarded":True,
        "dockAttachDeferredToWindowVisibility":True,
        "hostEntry":"ScarletIntegratedHostView",
        "realLCGuestModelsUsed":True,
        "originalGuestImporterPreserved":True,
        "embeddedSideStoreGuestUIEnabled":False,
        "embeddedSideStoreEnginePreserved":True,
        "nativeGuestManager":guest_manager,
        "originalNativeUIGlassEffect":True,
        "upstreamLiveContainerSourceUntouched":False,
        "upstreamLiveContainerModifiedTrackedPaths":[
            "LiveContainerSwiftUI/App/LiveContainerSwiftUIApp.swift",
            "MultitaskSupport/MultitaskAppWindow.swift",
            "MultitaskSupport/MultitaskDockView.swift",
            "LiveContainerSwiftUI/Views/AppList/LCAppListView.swift"
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
    print("[PASS] Crash-traced dock window force unwrap replaced by deferred, data-preserving mount")
    print("[PASS] Original LC guest IPA/URL import preserved; SideStore guest UI shortcuts removed (engine retained)")
    print("[PASS] New Figma Scarlet icon compiled into AppIcon.appiconset source; Xcode archive pending")
    print("[BLOCK] Await actual Xcode archive and iPhone runtime validation")
if __name__=="__main__":main()
