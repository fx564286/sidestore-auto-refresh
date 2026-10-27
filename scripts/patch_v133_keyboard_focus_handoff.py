#!/usr/bin/env python3
"""V133 keyboard focus ownership: foreground guest picker and minimization.

V46 intentionally prevents blind global responder resignation. V133 keeps that
rule, but explicitly closes the currently interactive guest's keyboard before
opening the common picker; only the same UIWindowScene's normal-level owner
may be dismissed. Do not alter direct guest keyboard behavior outside an
explicit user-triggered switch or a real owning view minimization.
"""
from pathlib import Path
import sys

DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
DEC = Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK = "SCARLET_V133_KEYBOARD_HANDOFF"
MIN = "SCARLET_V133_KEYBOARD_OWNER_MINIMIZE"


def once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"V133 {label}: expected 1 anchor, found {count}")
    return source.replace(old, new, 1)


def dock_patch(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or "keyboardOwner.endEditing(true)" not in source:
            raise ValueError("V133 partial picker patch")
        return source
    for marker in ("SCARLET_V132_GLASS_DRAG", "NRG_V46_GUEST_KEYBOARD_SCOPE",
                   "SCARLET_V129_PICKER_RESILIENCE"):
        if marker not in source:
            raise ValueError(f"V133 missing dock prerequisite: {marker}")
    anchor = '''        NSLog("[SCARLET_V129_PICKER_RESILIENCE] present=1 source_attached=1 direct=%d windowActions=%d", directMode ? 1 : 0, windowActions ? 1 : 0)
        let overlay = UIControl(frame: owner.bounds)'''
    replacement = '''        // SCARLET_V133_KEYBOARD_HANDOFF: explicitly presenting the picker
        // ends editing in the same foreground guest scene. The Direct fallback
        // button lives in a separate alert-level UIWindow; ending editing on
        // that alert window does not reach the real guest text responder.
        // NEVER broadcast process-wide resignFirstResponder or mutate a
        // keyboard belonging to a different UIWindowScene.
        let normalSceneWindow = owner.windowScene?.windows.first(where: { candidate in
            candidate.isKeyWindow && candidate.windowLevel == .normal &&
            !candidate.isHidden && candidate.alpha > 0.01
        }) ?? owner.windowScene?.windows.first(where: { candidate in
            candidate.windowLevel == .normal &&
            !candidate.isHidden && candidate.alpha > 0.01
        })
        let keyboardOwner = normalSceneWindow ?? owner
        let endedEditing = keyboardOwner.endEditing(true)
        if let decorated = controller as? DecoratedAppSceneViewController {
            decorated.appSceneVC.view.endEditing(true)
            decorated.appSceneVC.contentView?.endEditing(true)
        }
        NSLog("[SCARLET_V133_KEYBOARD] phase=picker owner_normal=%d editing_ended=%d direct=%d",
              keyboardOwner.windowLevel == .normal ? 1 : 0,
              endedEditing ? 1 : 0, directMode ? 1 : 0)
        NSLog("[SCARLET_V129_PICKER_RESILIENCE] present=1 source_attached=1 direct=%d windowActions=%d", directMode ? 1 : 0, windowActions ? 1 : 0)
        let overlay = UIControl(frame: owner.bounds)'''
    return once(source, anchor, replacement, "picker focus handoff")


def dec_patch(source: str) -> str:
    if MIN in source:
        if source.count(MIN) != 1 or "[self nrgV133ContainsActiveResponder:self.view]" not in source:
            raise ValueError("V133 partial minimization patch")
        return source
    for marker in ("NRG_V28_GUEST_LIFECYCLE", "NRG_V46_MINIMIZE_KEYBOARD_SCOPE"):
        if marker not in source:
            raise ValueError("V133 missing decorated prerequisite: "+marker)
    anchor = '''- (void)minimizeWindow {
    if (self.view.hidden) return;
    [self.view endEditing:YES];'''
    replacement = '''// SCARLET_V133_KEYBOARD_OWNER_MINIMIZE: check ownership BEFORE calling
// endEditing, since a successful resignation clears firstResponder status.
// Only the view actually being minimized may request its owning UIWindow
// to release a separate UIKit text-effect responder.
- (BOOL)nrgV133ContainsActiveResponder:(UIView *)root {
    if (!root) return NO;
    if (root.isFirstResponder) return YES;
    for (UIView *child in root.subviews) {
        if ([self nrgV133ContainsActiveResponder:child]) return YES;
    }
    return NO;
}

- (void)minimizeWindow {
    if (self.view.hidden) return;
    BOOL hadGuestResponder = [self nrgV133ContainsActiveResponder:self.view];
    [self.view endEditing:YES];'''
    source=once(source,anchor,replacement,"owner-responder helper")
    anchor = '''    [self.appSceneVC.contentView endEditing:YES];
    // NRG_V46_MINIMIZE_KEYBOARD_SCOPE: do not dismiss the shared UIWindow during old-guest minimization.'''
    replacement = '''    [self.appSceneVC.contentView endEditing:YES];
    if (hadGuestResponder && self.view.window != nil) {
        // V46 protection remains: never close an unrelated/shared host
        // responder unless THIS guest owned the first-responder chain.
        BOOL owningWindowClosed = [self.view.window endEditing:YES];
        NSLog(@"[SCARLET_V133_KEYBOARD] phase=minimize owner_focus=1 window_ended=%d",
              owningWindowClosed ? 1 : 0);
    }
    // NRG_V46_MINIMIZE_KEYBOARD_SCOPE: do not dismiss the shared UIWindow during old-guest minimization.'''
    return once(source,anchor,replacement,"owner-only minimize")


def apply(root: Path):
    planned=[]
    for rel,patch in ((DOCK,dock_patch),(DEC,dec_patch)):
        path=root/rel
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"V133 required file absent: {path}")
        old=path.read_text()
        new=patch(old)
        if patch(new)!=new:raise ValueError(f"V133 not idempotent {rel}")
        planned.append((path,old,new))
    for path,old,new in planned:
        if old!=new:path.write_text(new)
    print("[PASS] V133 keyboard editing ends only on explicit picker activation/owning guest minimize")


if __name__ == "__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v133_keyboard_focus_handoff.py <LiveContainer root>")
    apply(Path(sys.argv[1]))
