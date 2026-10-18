#!/usr/bin/env python3
"""V46: scope guest keyboard handoff to the actual owning UIKit window.

Pinned V27/V28 multitask source only. No global first-responder broadcast,
no host/target window-wide endEditing, no guest termination or dock changes.
"""
from pathlib import Path
import sys

MARK="NRG_V46_KEYBOARD_WINDOW_SCOPE"
DOCK="MultitaskSupport/MultitaskDockView.swift"
DEC="MultitaskSupport/DecoratedAppSceneViewController.m"
MINIMIZE_MARK="NRG_V46_MINIMIZE_KEYBOARD_SCOPE"

def replace_once(text,old,new,label):
    count=text.count(old)
    if count!=1: raise RuntimeError(f"V46 {label}: expected 1 anchor; found {count}")
    return text.replace(old,new,1)

def patch(source):
    if MARK in source:
        assert source.count(MARK)==3, "V46 patch marker count wrong"
        focus = source.split("private func prepareKeyboardForGuestSwitch",1)[-1]
        focus = focus.split("private func passURLSchemeToView",1)[0]
        assert "window.endEditing(true)" not in focus
        assert "UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder)" not in focus
        return source
    for required in ("NRG_V27_GUEST_SWITCH_LIFECYCLE", "NRG_V28_GUEST_LIFECYCLE",
                     "NRG_V27_GEOMETRY_FADE_ONLY"):
        if required not in source: raise RuntimeError("V46 requires existing V27/V28: "+required)
    source=replace_once(source,
'''        guard let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene else {
            return false
        }

        for window in windowScene.windows {''',
'''        // NRG_V46_KEYBOARD_WINDOW_SCOPE: never select the first arbitrary scene.
        // The guest itself is authoritative for which host window owns it.
        guard let guest = apps.first(where: { $0.appUUID == uuid })?.view,
              let owningWindow = guest.window,
              let windowScene = owningWindow.windowScene else {
            NSLog("[NRG_V46_KEYBOARD] target has no attached window; switch skipped")
            return false
        }

        for window in windowScene.windows {''',"owning UIWindowScene")
    source=replace_once(source,
'''    private func findMultitaskView(in view: UIView, withUUID uuid: String) -> UIView? {
        apps.first { $0.appUUID == uuid }?.view
    }''',
'''    // NRG_V46_KEYBOARD_WINDOW_SCOPE: only the guest's real UIWindow can own its
    // switch operation; do not return the same view for every candidate window.
    private func findMultitaskView(in view: UIView, withUUID uuid: String) -> UIView? {
        guard let candidateWindow = view as? UIWindow,
              let guest = apps.first(where: { $0.appUUID == uuid })?.view,
              guest.window === candidateWindow else { return nil }
        return guest
    }''',"window-scoped lookup")
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
    new='''        // NRG_V46_KEYBOARD_WINDOW_SCOPE: focus cleanup applies only to previous
        // guest scenes in this window scene. Never resign the *target* guest or
        // broadcast resignFirstResponder across every UIKit window.
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
                // Preserve the V28 foreground state protocol and PiP exception.
                if PiPManager.shared?.isPiP(withDecoratedVC: vc) != true {
                    vc.appSceneVC.lcSetGuestSceneForeground(false)
                }
            }
            previousGuests += 1
        }
        NSLog("[NRG_V46_KEYBOARD] previous_guests=%ld scoped=1 target_resigned=0 global_resign=0", previousGuests)'''
    source=replace_once(source,old,new,"remote responder cleanup")
    assert source.count(MARK)==3, "V46 patch marker count mismatch"
    return source

def patch_minimize(source):
    if MINIMIZE_MARK in source:
        assert source.count(MINIMIZE_MARK)==1, "V46 minimize marker count wrong"
        assert "[self.view.window endEditing:YES];" not in source
        return source
    if "NRG_V28_GUEST_LIFECYCLE" not in source:
        raise RuntimeError("V46 requires V28 guest minimization policy")
    # Asynchronous minimizeAllWindows can run after another guest starts editing
    # in the same shared host UIWindow. This global endEditing would dismiss the
    # new guest's keyboard. Existing guest-view scopes suffice.
    return replace_once(source,
        "    [self.view.window endEditing:YES];\n",
        "    // "+MINIMIZE_MARK+": do not resign the shared host UIWindow during old-guest minimization.\n",
        "avoid host-wide keyboard resignation during minimize")

def main(root):
    root=Path(root)
    targets=((root/DOCK,patch),(root/DEC,patch_minimize))
    changes=[]
    for path,fn in targets:
        original=path.read_text(encoding="utf-8")
        updated=fn(original)
        assert fn(updated)==updated,"non-idempotent V46 patch"
        changes.append((path,original,updated))
    for path,original,updated in changes:
        if updated!=original:path.write_text(updated,encoding="utf-8")
    print("[PASS] V46 correct UIWindow + previous-guest-only focus; no shared-window/global resign")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v46_keyboard_window_scope.py <pinned-LiveContainer>")
    main(sys.argv[1])
