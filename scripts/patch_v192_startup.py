#!/usr/bin/env python3
"""V192: defer iOS 27 launch-time Dock singleton, keep existing guest identities."""
from pathlib import Path
import plistlib
import sys

MARK = "NRG_V192_SCARLET_STARTUP"
DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
SHELL = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
INFO = Path("LiveContainer/Info.plist")

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one anchor; found {count}")
    return text.replace(old, new, 1)

def patch_dock(src):
    if MARK in src:
        if "public lazy var windowHostingView" not in src:
            raise RuntimeError("V192 partial Dock patch")
        return src
    if "NRG_V191_STARTUP_HOST_ATTACH" not in src:
        raise RuntimeError("V191 base is required")
    src = replace_once(src,
        "    @objc public var windowHostingView = VirtualWindowsHostView()",
        "    // NRG_V192_SCARLET_STARTUP: UIKit scene can be absent at init time.\n"
        "    @objc public lazy var windowHostingView = VirtualWindowsHostView()",
        "lazy virtual host")
    init_start = src.index("    override init() {")
    init_end = src.index("\n    deinit {", init_start)
    init_block = src[init_start:init_end]
    init_block = replace_once(init_block,
        "        nrgV191AttachGuestWindowHostIfReady()",
        "        // V192: defer UIKit host attachment until first scene commit.",
        "no eager host attachment")
    src = src[:init_start] + init_block + src[init_end:]
    src = replace_once(src,
        "        let anchor = root.subviews.first(where: { $0 !== windowHostingView }) ?? root",
        "        guard root.window === window, !root.bounds.isEmpty,\n"
        "              let anchor = root.subviews.first(where: { !$0.bounds.isEmpty }) else { return }\n"
        "        guard anchor !== windowHostingView else { return }",
        "attach only to live UIKit root child")
    return src

def patch_shell(src):
    if MARK in src:
        if "nrgV192RefreshIslandIfReady" not in src:
            raise RuntimeError("V192 partial shell patch")
        return src
    old = """        .onAppear {
            if #available(iOS 16.0, *) {
                MultitaskDockManager.shared.nrgV58RefreshNativeIsland()
            }
        }
        .onReceive(sharedModel.$apps) { _ in
            DispatchQueue.main.async {
                if #available(iOS 16.0, *) {
                    MultitaskDockManager.shared.nrgV58RefreshNativeIsland()
                }
            }
        }
"""
    new = """        // NRG_V192_SCARLET_STARTUP: SwiftUI first commit precedes UIKit root.
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                nrgV192RefreshIslandIfReady()
            }
        }
        .onReceive(sharedModel.$apps) { _ in
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                nrgV192RefreshIslandIfReady()
            }
        }
"""
    src = replace_once(src, old, new, "deferred V60 callbacks")
    src += """
// V192: ignore native-Island refresh during the uncommitted first scene.
// No app-signing state, guest container, or URL routing changes.
@MainActor
private func nrgV192RefreshIslandIfReady() {
    guard UIApplication.shared.connectedScenes
        .compactMap({ $0 as? UIWindowScene })
        .contains(where: { scene in
            scene.activationState == .foregroundActive &&
                scene.windows.contains(where: { window in
                    guard window.isKeyWindow, !window.bounds.isEmpty,
                          let root = window.rootViewController?.view,
                          root.window === window, !root.subviews.isEmpty else { return false }
                    return true
                })
        }) else { return }
    if #available(iOS 16.0, *) {
        MultitaskDockManager.shared.nrgV58RefreshNativeIsland()
    }
}
"""
    return src

def main(root):
    pending=[]
    for rel, patch in ((DOCK,patch_dock),(SHELL,patch_shell)):
        path=root/rel
        before=path.read_text(encoding="utf-8")
        after=patch(before)
        if patch(after)!=after: raise RuntimeError(f"non-idempotent patch: {rel}")
        pending.append((path,before,after))
    info_path=root/INFO
    info=plistlib.loads(info_path.read_bytes())
    if info.get("CFBundleIdentifier") not in ("$(PRODUCT_BUNDLE_IDENTIFIER)", "com.kdt.livecontainer"):
        raise RuntimeError("Refusing to alter unknown host bundle identity")
    info["CFBundleDisplayName"]="Scarlet Crystal"
    info["CFBundleName"]="Scarlet Crystal"
    info["CFBundleVersion"]="3.8.192"
    for path,before,after in pending:
        if before!=after:
            path.write_text(after,encoding="utf-8")
    info_path.write_bytes(plistlib.dumps(info))
    print("[PASS] V192 guarded native island startup, deferred window host, Scarlet Crystal branding")
    print("[PASS] Original host identifier and provisioning strategy preserved")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v192_startup.py <LiveContainer>")
    main(Path(sys.argv[1]))
