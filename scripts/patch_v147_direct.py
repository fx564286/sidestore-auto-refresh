#!/usr/bin/env python3
"""V147 Direct button repair from V144: preserve one UIButton and host picker.

No new popup, dock, UIWindow, bundle ID or extension. Pan cannot cancel a
genuine tap; delivery to the existing host is logged separately from acceptance.
"""
from pathlib import Path
import sys
BOOT=Path("LiveContainer/LCBootstrap.m")
SHELL=Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
MARK="SCARLET_V147_DIRECT_TAP_OWNER"
HOSTMARK="SCARLET_V147_DIRECT_HOST_ROUTING"

def once(s,a,b,label):
    n=s.count(a)
    if n!=1:raise ValueError(f"V147 Direct {label}: expected 1 anchor got {n}")
    return s.replace(a,b,1)

def boot(s):
    if MARK in s:
        if s.count(MARK)!=1 or "drag.cancelsTouchesInView = NO" not in s:
            raise ValueError("V147 partial Direct")
        return s
    for token in ("SCARLET_V139_UNIFIED_GUEST_ACTION",
                  "SCARLET_V144_BUTTON_LENS","SCGuestMorphPresenter"):
        if token not in s:raise ValueError("V147 Direct missing V144 "+token)
    s=once(s,'''    [handle addGestureRecognizer:drag];
    [vc.view addSubview:handle];''',
        '''    // SCARLET_V147_DIRECT_TAP_OWNER: UIKit pan must not swallow
    // the sole existing button's touchUpInside event.
    drag.cancelsTouchesInView = NO;
    [handle addGestureRecognizer:drag];
    [vc.view addSubview:handle];''',"disable pan cancellation")
    s=once(s,'    NSLog(@"[SCARLET_V114_UI] tap=1 mode=direct");',
        '''    NSLog(@"[SCARLET_V114_UI] tap=1 mode=direct");
    NSLog(@"[SCARLET_V147_DIRECT] event=tap delivered=existing_button");''',
        "Direct tap evidence")
    return s

def shell(s):
    if HOSTMARK in s:
        if s.count(HOSTMARK)!=1 or "result=presented" not in s:
            raise ValueError("V147 host partial")
        return s
    if "SCARLET_V139_UNIFIED_GUEST_ACTION" not in s or "nrg-guest-controls" not in s:
        raise ValueError("V147 missing V144 host route")
    prefix='''        // SCARLET_V139_UNIFIED_GUEST_ACTION: Classic/Direct'''
    start=s.index(prefix)
    end=s.index("\n            return\n        }",start)+len("\n            return\n        }")
    old=s[start:end]
    for must in ('url.host?.lowercased() == "nrg-guest-controls"',
                 "sharedModel.selectedTab = .apps",
                 "nrgV72PresentGuestSwitcher("):
        if must not in old:raise ValueError("V147 missing host route "+must)
    new='''        // SCARLET_V147_DIRECT_HOST_ROUTING: the same host-owned picker,
        // never a second button, panel or UIWindow. A host scene may only
        // become active after the existing Direct guest hands off.
        if url.scheme?.lowercased() == "scarletcrystal251",
           url.host?.lowercased() == "nrg-guest-controls" {
            sharedModel.selectedTab = .apps
            var delivered = false
            for delay in [0.0, 0.22, 0.60] {
                DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                    guard !delivered else { return }
                    let scene = UIApplication.shared.connectedScenes
                        .compactMap { $0 as? UIWindowScene }
                        .first { $0.activationState == .foregroundActive }
                    guard let hostWindow = scene?.windows.first(where: {
                        !$0.isHidden && $0.windowLevel == .normal &&
                        $0.rootViewController != nil && $0.alpha > 0.01
                    }), let root = hostWindow.rootViewController,
                    root.view.window === hostWindow else {
                        NSLog("[SCARLET_V147_DIRECT] route=host result=not_ready")
                        return
                    }
                    if #available(iOS 16.0, *) {
                        delivered = true
                        MultitaskDockManager.shared.nrgV72PresentGuestSwitcher(
                            from: root, sourceView: root.view)
                        NSLog("[SCARLET_V147_DIRECT] route=host result=presented")
                    }
                }
            }
            return
        }'''
    return s[:start]+new+s[end:]

def apply(root):
    entries=[]
    for path,patch in ((BOOT,boot),(SHELL,shell)):
        file=root/path
        if not file.is_file() or file.is_symlink():raise ValueError("V147 missing pinned "+str(path))
        before=file.read_text(encoding="utf-8")
        after=patch(before)
        if patch(after)!=after:raise ValueError("V147 Direct idempotence failed "+str(path))
        entries.append((file,before,after))
    for path,before,after in entries:
        if before!=after:path.write_text(after,encoding="utf-8")
    print("[PASS] V147 Direct existing button tap and single host route")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v147_direct.py <LiveContainer>")
    apply(Path(sys.argv[1]))
