#!/usr/bin/env python3
"""V145: retain single Direct button and make its event/host handoff observable.

Do not create a second picker or a new UIWindow; repair the existing Direct
UIButton's pan-vs-tap arbitration and the existing host deep-link dispatcher.
"""
from pathlib import Path
import sys
BOOT=Path("LiveContainer/LCBootstrap.m")
SHELL=Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
MARK="SCARLET_V145_DIRECT_ACTION_REPAIR"

def once(s,a,b,label):
    n=s.count(a)
    if n!=1:raise ValueError(f"V145 {label}: {n} anchors")
    return s.replace(a,b,1)

def boot(s):
    if MARK in s:
        if s.count(MARK)!=1 or "drag.cancelsTouchesInView = NO;" not in s:
            raise ValueError("V145 Direct partial")
        return s
    if "SCARLET_V139_UNIFIED_GUEST_ACTION" not in s:
        raise ValueError("V145 Direct requires V139 URL routing")
    s=once(s,
        '''    [handle addGestureRecognizer:drag];
    [vc.view addSubview:handle];''',
        '''    // SCARLET_V145_DIRECT_ACTION_REPAIR: the drag recognizer must
    // not cancel the same UIButton touchUpInside event used to open picker.
    drag.cancelsTouchesInView = NO;
    [handle addGestureRecognizer:drag];
    [vc.view addSubview:handle];''',
        "cancelled tap by pan recognizer")
    s=once(s,
        '''    NSLog(@"[SCARLET_V114_UI] tap=1 mode=direct");''',
        '''    NSLog(@"[SCARLET_V114_UI] tap=1 mode=direct");
    NSLog(@"[SCARLET_V145_DIRECT] event=tap owner=existing_button");''',
        "Direct tap diagnostic")
    s=once(s,
        '''    NSURL *returnURL = [NSURL URLWithString:@"scarletcrystal251://nrg-guest-controls"];''',
        '''    NSURL *returnURL = [NSURL URLWithString:@"scarletcrystal251://nrg-guest-controls"];
    NSLog(@"[SCARLET_V145_DIRECT] route=host_link request=picker");''',
        "visible Direct host request")
    return s

def shell(s):
    mark="SCARLET_V145_DIRECT_HOST_DELIVERY"
    if mark in s:
        if s.count(mark)!=1 or "route=host_picker result=presented" not in s:
            raise ValueError("V145 host dispatch partial")
        return s
    start=s.index("        // SCARLET_V139_UNIFIED_GUEST_ACTION: Classic/Direct")
    stop=s.index("\n            return\n        }",start)+len("\n            return\n        }")
    section=s[start:stop]
    for required in ('url.host?.lowercased() == "nrg-guest-controls"',
                     "sharedModel.selectedTab = .apps",
                     "MultitaskDockManager.shared.nrgV72PresentGuestSwitcher"):
        if required not in section:raise ValueError("V145 missing existing URL route")
    replacement='''        // SCARLET_V145_DIRECT_HOST_DELIVERY: a Direct guest cannot assume
        // that host UIWindow exists at the instant openURL completes.
        // Retry only on the host's active normal-level window; retain a
        // single presentation path and never claim accepted URL = opened UI.
        if url.scheme?.lowercased() == "scarletcrystal251",
           url.host?.lowercased() == "nrg-guest-controls" {
            sharedModel.selectedTab = .apps
            var delivered = false
            for delay in [0.0, 0.20, 0.55] {
                DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
                    if delivered { return }
                    let scene = UIApplication.shared.connectedScenes
                        .compactMap { $0 as? UIWindowScene }
                        .first { $0.activationState == .foregroundActive }
                    guard let hostWindow = scene?.windows.first(where: {
                        !$0.isHidden && $0.windowLevel == .normal &&
                        $0.rootViewController != nil && $0.alpha > 0.01
                    }), let root = hostWindow.rootViewController,
                    root.view.window === hostWindow else {
                        NSLog("[SCARLET_V145_DIRECT] route=host_picker result=host_not_ready")
                        return
                    }
                    if #available(iOS 16.0, *) {
                        delivered = true
                        MultitaskDockManager.shared.nrgV72PresentGuestSwitcher(
                            from: root, sourceView: root.view)
                        NSLog("[SCARLET_V145_DIRECT] route=host_picker result=presented")
                    }
                }
            }
            return
        }'''
    return s[:start]+replacement+s[stop:]

def apply(root):
    changes=[]
    for path,func in ((BOOT,boot),(SHELL,shell)):
        f=root/path
        if not f.is_file() or f.is_symlink():
            raise ValueError("V145 missing "+str(f))
        old=f.read_text(encoding="utf-8")
        new=func(old)
        if func(new)!=new:raise ValueError("V145 not idempotent "+str(path))
        changes.append((f,old,new))
    for f,old,new in changes:
        if old!=new:f.write_text(new,encoding="utf-8")
    print("[PASS] V145 Direct button pan/tap ownership + one host picker route")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v145_direct_action.py <LiveContainer>")
    apply(Path(sys.argv[1]))
