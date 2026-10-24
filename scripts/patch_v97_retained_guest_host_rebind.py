#!/usr/bin/env python3
"""V97: safely reattach a still-live virtual guest's existing UIKit view.

Never create a second LiveProcess, clear container ownership, restart host,
or terminate an unknown/live guest as a substitute for restoring its window.
"""
from pathlib import Path
import sys

TARGET = Path("MultitaskSupport/MultitaskDockView.swift")
MARKER = "SCARLET_V97_RETAINED_GUEST_HOST_REBIND"
OLD = '''        guard let window = targetView.window else {
            print("[LC_RETURN] RETURN_FAILED reason=retained_view_has_no_window")
            return false
        }'''
NEW = '''        // SCARLET_V97_RETAINED_GUEST_HOST_REBIND: the surviving guest's
        // decorated view may be orphaned when iOS rebuilds the HOST scene.
        // First try the existing host attachment path. Only move the SAME
        // already-owned view if its prior parent is not in any UIWindow and
        // this host is truly foreground; never launch a replacement process.
        if targetView.window == nil && controller.appSceneVC.isAppRunning {
            nrgV191AttachGuestWindowHostIfReady()
            if targetView.window == nil,
               targetView.superview?.window == nil,
               controller.parent != nil,
               let hostWindow = windowHostingView.window,
               hostWindow.windowScene?.activationState == .foregroundActive,
               windowHostingView.bounds.width > 0,
               windowHostingView.bounds.height > 0 {
                windowHostingView.addSubview(targetView)
                NSLog("[SCARLET_V97_GUEST] retained_view_rebound=1 same_controller=1")
            }
        }
        guard let window = targetView.window else {
            NSLog("[SCARLET_V97_GUEST] retained_view_rebound=0 running=%d has_parent=%d host_attached=%d",
                  controller.appSceneVC.isAppRunning ? 1 : 0,
                  controller.parent != nil ? 1 : 0,
                  windowHostingView.window != nil ? 1 : 0)
            print("[LC_RETURN] RETURN_FAILED reason=retained_view_has_no_window")
            return false
        }'''

def patch(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1 or NEW not in source:
            raise ValueError("V97 partial/duplicate retained-view recovery")
        return source
    if source.count(OLD) != 1:
        raise ValueError(f"V97 expected exactly one verified docking anchor: {source.count(OLD)}")
    if 'func bringMultitaskViewToFront(uuid:' not in source or 'nrgV191AttachGuestWindowHostIfReady()' not in source:
        raise ValueError("V97 upstream host/reopen API not present")
    return source.replace(OLD, NEW, 1)

def apply(root: Path) -> None:
    file = root / TARGET
    original = file.read_text(encoding="utf-8")
    after = patch(original)
    if patch(after) != after:
        raise ValueError("V97 idempotency failed")
    if original != after:
        file.write_text(after, encoding="utf-8")
    print("[PASS] V97 same-live-guest view host rebinding; no replacement launch")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v97_retained_guest_host_rebind.py <LiveContainer-source>")
    apply(Path(sys.argv[1]))
