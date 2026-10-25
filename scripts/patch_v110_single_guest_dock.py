#!/usr/bin/env python3
"""V110: a one-guest floating dock has no switching utility.

The V108 blue chevron was deleted, but its expanded UI still renders a single
guest icon over SideStore/guest content. Suppress the actual view and hit area
unless 2+ installed running guests exist. Keep the multi-guest switcher,
native window-control overflow, Direct confirmation, and viewport untouched.
"""
from pathlib import Path
import sys

REL = Path("MultitaskSupport/MultitaskDockView.swift")
MARKER = "SCARLET_V110_SINGLE_GUEST_DOCK_SUPPRESSED"

def one(src, old, new, part):
    count=src.count(old)
    if count!=1:
        raise ValueError(f"V110 {part}: expected unique source, got {count}")
    return src.replace(old,new,1)

def transform(src):
    if MARKER in src:
        audit(src)
        return src
    if "SCARLET_V108_NO_BLUE_COLLAPSED_DOCK" not in src:
        raise ValueError("V110 requires V108 dock removal first")
    start=src.index("public struct MultitaskDockSwiftView: View")
    end=src.index("// MARK: - Minimize All Button View",start)
    left, dock, right=src[:start],src[start:end],src[end:]
    dock=one(dock,
        "               !dockManager.isDockHidden && !dockManager.apps.isEmpty {",
        """               !dockManager.isDockHidden && dockManager.apps.count > 1 {
                // SCARLET_V110_SINGLE_GUEST_DOCK_SUPPRESSED:
                // one running guest has nothing to switch to.""",
        "one-guest rendering condition")
    dock=one(dock,'''        .ignoresSafeArea()
        .gesture(''',
        '''        .ignoresSafeArea()
        // Empty GeometryReader must not swallow touch input for a single guest.
        .allowsHitTesting(dockManager.apps.count > 1)
        .gesture(''', "one-guest touch shield")
    src=left+dock+right
    src=one(src,
        '''        if isDockHidden {
            let leftEdgeGesture = UIScreenEdgePanGestureRecognizer(target: self, action: #selector(handleEdgeSwipe(_:)))''',
        '''        if isDockHidden && apps.count > 1 {
            let leftEdgeGesture = UIScreenEdgePanGestureRecognizer(target: self, action: #selector(handleEdgeSwipe(_:)))''',
        "edge gesture only for multiple guests")
    src=one(src,
        '''        guard isDockHidden, (gesture.state == .began || gesture.state == .changed) else { return }''',
        '''        guard isDockHidden, apps.count > 1,
              (gesture.state == .began || gesture.state == .changed) else { return }''',
        "edge swipe only with alternatives")
    audit(src)
    return src

def audit(src):
    for required in (
        MARKER, "dockManager.apps.count > 1",
        ".allowsHitTesting(dockManager.apps.count > 1)",
        "if isDockHidden && apps.count > 1 {",
        "guard isDockHidden, apps.count > 1,",
        "ForEach(dockManager.apps) { app in",
        "SCARLET_V108_NO_BLUE_COLLAPSED_DOCK",
        "nrgV102PresentWindowActionsFrom"):
        if required not in src:
            raise ValueError("V110 missing live guest route: "+required)
    if "struct CollapsedDockView: View" in src or "CollapsedDockView(isHidden:" in src:
        raise ValueError("V110 old blue button source regressed")
    dock=src[src.index("public struct MultitaskDockSwiftView: View"):
             src.index("// MARK: - Minimize All Button View")]
    if "!dockManager.isDockHidden && !dockManager.apps.isEmpty" in dock:
        raise ValueError("V110 one-guest overlay still visible")

def apply(root: Path):
    p=root/REL
    if not p.is_file() or p.is_symlink():
        raise ValueError("V110 missing pinned Swift Dock")
    old=p.read_text(encoding="utf-8")
    new=transform(old)
    if transform(new)!=new:
        raise ValueError("V110 non-idempotent dock")
    if new!=old:p.write_text(new,encoding="utf-8")
    print("[PASS] V110 single running guest no overlay or touch region; >1 guest switch preserved")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v110_single_guest_dock.py <LiveContainer>")
    apply(Path(sys.argv[1]))
