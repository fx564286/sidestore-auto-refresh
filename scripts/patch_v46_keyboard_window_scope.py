#!/usr/bin/env python3
"""V46: prevent cross-guest keyboard dismissal in existing LiveContainer.

The existing guest-return patch already selects the owning targetView.window.
Keep it. Fix only global-responder and shared-window dismissal in V27/V28.
Preserve Dock, PiP, scene lifecycle, guest process, settings, and Refresh.
"""
from pathlib import Path
import sys

MARK="NRG_V46_GUEST_KEYBOARD_SCOPE"
MINIMIZE_MARK="NRG_V46_MINIMIZE_KEYBOARD_SCOPE"
DOCK="MultitaskSupport/MultitaskDockView.swift"
DEC="MultitaskSupport/DecoratedAppSceneViewController.m"

def replace_once(source,old,new,label):
    count=source.count(old)
    if count!=1: raise RuntimeError(f"V46 {label}: expected 1 anchor; found {count}")
    return source.replace(old,new,1)

def patch(source):
    if MARK in source:
        assert source.count(MARK)==1, "V46 keyboard patch is duplicated"
        focus=source.split("private func prepareKeyboardForGuestSwitch",1)[-1]
        focus=focus.split("private func passURLSchemeToView",1)[0]
        assert "window.endEditing(true)" not in focus
        assert "UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder)" not in focus
        return source
    for required in ("NRG_V27_GUEST_SWITCH_LIFECYCLE","NRG_V28_GUEST_LIFECYCLE",
                     "NRG_V27_GEOMETRY_FADE_ONLY",
                     "guard let window = targetView.window else"):
        if required not in source:raise RuntimeError("V46 requires existing pinned guest-owner and V27/V28: "+required)
    # V28 currently closes old guests' view responder chains correctly, then
    # erroneously resigns the *entire* UIWindow and sends a global resign.
    old='''        var previousGuests = 0
        for app in apps {
            guard let old = app.view, old !== targetView, old.window === window else { continue }
            // NRG_V28_GUEST_LIFECYCLE: close remote responder and background old scene.
            old.endEditing(true)
            if let vc = old._viewDelegate() as? DecoratedAppSceneViewController {
                vc.appSceneVC.view.endEditing(true)
                vc.appSceneVC.contentView?.endEditing(true)
                if PiPManager.shared?.isPiP(withDecoratedVC: vc) != true {
                    vc.appSceneVC.lcSetGuestSceneForeground(false)
                }
            }
            previousGuests += 1
        }
        window.endEditing(true)
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder),
                                       to: nil, from: nil, for: nil)
        NSLog("[NRG_V27_GUEST_FOCUS] previous_guests=%ld resign_requested=1", previousGuests)'''
    new='''        // NRG_V46_GUEST_KEYBOARD_SCOPE: previous guest responders only.
        // Never resign the target guest or send global resign to every window.
        guard let targetScene = window.windowScene else { return }
        var previousGuests = 0
        for app in apps {
            guard let old = app.view, old !== targetView,
                  let oldWindow = old.window,
                  oldWindow.windowScene === targetScene else { continue }
            old.endEditing(true)
            if let vc = old._viewDelegate() as? DecoratedAppSceneViewController {
                vc.appSceneVC.view.endEditing(true)
                vc.appSceneVC.contentView?.endEditing(true)
                if PiPManager.shared?.isPiP(withDecoratedVC: vc) != true {
                    vc.appSceneVC.lcSetGuestSceneForeground(false)
                }
            }
            previousGuests += 1
        }
        NSLog("[NRG_V46_KEYBOARD] previous_guests=%ld scoped=1 target_resigned=0 global_resign=0", previousGuests)'''
    return replace_once(source,old,new,"previous-guest focus cleanup")

def patch_minimize(source):
    if MINIMIZE_MARK in source:
        assert source.count(MINIMIZE_MARK)==1, "V46 minimize patch is duplicated"
        assert "[self.view.window endEditing:YES];" not in source
        return source
    if "NRG_V28_GUEST_LIFECYCLE" not in source:
        raise RuntimeError("V46 requires V28 minimization lifecycle")
    # minimizeAllWindows is asynchronous; when its callback runs, another
    # guest may already be editing in the *same* host UIWindow. View-specific
    # resign above remains unchanged; suppress only the shared-window call.
    return replace_once(source,
        "    [self.view.window endEditing:YES];\n",
        "    // "+MINIMIZE_MARK+": do not dismiss the shared UIWindow during old-guest minimization.\n",
        "host-wide keyboard dismissal on minimize")

def main(root):
    root=Path(root)
    planned=[]
    for rel,fn in ((DOCK,patch),(DEC,patch_minimize)):
        path=root/rel
        before=path.read_text(encoding="utf-8")
        after=fn(before)
        assert fn(after)==after,"V46 patch is not idempotent"
        planned.append((path,before,after))
    # Validate both before writing either.
    for path,before,after in planned:
        if before!=after:path.write_text(after,encoding="utf-8")
    print("[PASS] V46 guest-only keyboard focus; shared-window/global resign removed; owned-window path preserved")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v46_keyboard_window_scope.py <pinned-LiveContainer>")
    main(sys.argv[1])
