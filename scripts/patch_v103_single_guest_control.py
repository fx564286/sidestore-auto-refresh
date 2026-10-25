#!/usr/bin/env python3
"""V103: one active guest control per execution mode + immediate switch.

Only the host-owned V73 floating control exists inside a decorated virtual
guest. The original LCReturnControl is used solely by undeco­rated Direct/
LiveProcess guests; V41's unconditional early-return previously left V76/V102
native button code unreachable. Never destroy the guest process or profile.
"""
from pathlib import Path
import sys

DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
NATIVE=Path("MultitaskSupport/AppSceneViewController.m")
VIRTUAL=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK_NATIVE="SCARLET_V103_SINGLE_CONTROL_OWNER"
MARK_DOCK="SCARLET_V103_IMMEDIATE_GUEST_SWITCH"
MARK_VIRTUAL="SCARLET_V103_VIRTUAL_ONLY_CONTROL"

def only(s, before, after, name):
    count=s.count(before)
    if count != 1: raise ValueError(f"V103 {name}: expected one anchor, got {count}")
    return s.replace(before,after,1)

def patch_native(s):
    if MARK_NATIVE in s:
        if s.count(MARK_NATIVE)!=1 or "return;\n    if (!self.lcReturnControl)" in s:
            raise ValueError("V103 native partial owner")
        return s
    for tok in ("NRG_V41_FLOATING_RETURN_REMOVED","SCARLET_V102_NATIVE_GESTURE_CLEANUP",
                "LC_GUEST_SWITCH_V76_PATCHED"):
        if tok not in s:raise ValueError("Missing previous native control stage: "+tok)
    old='''    // NRG_V41_FLOATING_RETURN_REMOVED: do not create an overlapping guest-return overlay.
    [self.lcReturnControl removeFromSuperview];
    self.lcReturnControl = nil;
    return;
    if (!self.lcReturnControl) {'''
    new='''    // SCARLET_V103_SINGLE_CONTROL_OWNER: an AppScene inside DecoratedVC
    // MUST NOT mount the old blue Return control. Its parent already owns
    // the ONE draggable V73 guest-control overlay. Native Direct guests
    // own precisely one LCReturnControl instead.
    const BOOL virtualWindowGuest =
        [self.delegate isKindOfClass:DecoratedAppSceneViewController.class];
    if (virtualWindowGuest) {
        if (self.lcReturnControl) {
            [self.lcReturnControl removeFromSuperview];
            self.lcReturnControl = nil;
        }
        NSLog(@"[SCARLET_V103_CONTROL] owner=virtual_v73 native=removed");
        return;
    }
    if (!self.lcReturnControl) {'''
    s=only(s,old,new,"V41 dead unconditional guard")
    s=only(s,
        '''    self.button.accessibilityLabel = @"Return to LiveContainer";''',
        '''    self.button.accessibilityLabel = @"Switch recently active guest apps";
    self.button.accessibilityIdentifier = @"scarlet.v103.native.guest.control";''',
        "native identity")
    s=only(s,
        '''    self.button.accessibilityHint = @"Minimizes this guest without closing it";''',
        '''    self.button.accessibilityHint = @"Tap: recent guest apps. Hold: window actions. Drag: move.";''',
        "native hint")
    s=only(s,
        '''    self.button.accessibilityLabel = self.collapsed ? @"Show Return to LiveContainer" : @"Return to LiveContainer";''',
        '''    self.button.accessibilityLabel = @"Recent guest apps";''',
        "native dynamic label")
    s=only(s,
        '''    if (self.collapsed) {
        self.collapsed = NO;
        [self setNeedsLayout];
        NSLog(@"[LC_RETURN] CONTROL_RESTORED");
        return;
    }''',
        '''    if (self.collapsed) {
        // V103: a collapsed button still opens the switcher in one tap.
        self.collapsed = NO;
        [self setNeedsLayout];
        NSLog(@"[SCARLET_V103_CONTROL] restored_and_dispatched=1");
    }''',
        "remove double-tap restore")
    s=only(s,
        '''        if ([NSUserDefaults.lcSharedDefaults boolForKey:@"LCGuestReturnStartsCollapsed"]) [self collapse];
        self.action();''',
        '''        self.action();''',
        "prevent trigger collapse before host panel")
    return s

def patch_virtual(s):
    if MARK_VIRTUAL in s:
        if s.count(MARK_VIRTUAL)!=1:return _fail("V103 virtual partial")
        return s
    for tok in ("SCARLET_V102_UNIFIED_ACTION_SURFACE","SCARLET_V100_TAP_OPEN"):
        if tok not in s:raise ValueError("Missing virtual control prerequisite "+tok)
    s=only(s,
           '''    overflow.accessibilityLabel = @"Guest window controls";''',
           '''    // SCARLET_V103_VIRTUAL_ONLY_CONTROL: the single virtual guest
    // overlay; do not resurrect the child AppScene blue Return control.
    overflow.accessibilityIdentifier = @"scarlet.v103.virtual.guest.control";
    overflow.accessibilityLabel = @"Guest switching and window actions";''',
           "unique V73 virtual identity")
    return s

def patch_dock(s):
    if MARK_DOCK in s:
        if s.count(MARK_DOCK)!=1 or "defer { dismissSelection() }" not in s:
            raise ValueError("V103 dock partial")
        return s
    for tok in ("SCARLET_V102_RECENT_FOCUS_CLOCK","SCARLET_V102_UNIFIED_ACTION_SURFACE",
                "SCARLET_V100_MORPH_PICKER"):
        if tok not in s:raise ValueError("Missing V102 dock stage "+tok)
    # One guest action owner in V100's morph render, no second CTA/UIAlert.
    old='''            item.addAction(UIAction { [weak self] _ in
                collapse {
                    guard let self else { return }'''
    new='''            item.addAction(UIAction { [weak self] _ in
                // SCARLET_V103_IMMEDIATE_GUEST_SWITCH: selecting a row
                // dispatches to the retained app NOW, not after the 0.28s
                // collapse animation. Selection closes the overlay instantly
                // while empty-space dismissal retains its spring transition.
                let dismissSelection: () -> Void = {
                    overlay.removeFromSuperview()
                    if dockView?.window?.windowScene === owner.windowScene {
                        dockView?.isHidden = previousDockHidden
                    }
                    sourceView.isHidden = false
                }
                defer { dismissSelection() }
                guard let self else { return }'''
    s=only(s,old,new,"execute selected guest before animation")
    after='''                    NSLog("[SCARLET_V102_RECENT] no_inactive_launch_path=1")
                }
            }, for: .touchUpInside)'''
    changed='''                    NSLog("[SCARLET_V102_RECENT] no_inactive_launch_path=1")
            }, for: .touchUpInside)'''
    s=only(s,after,changed,"remove obsolete asynchronous completion wrapper")
    return s

def _fail(message):raise ValueError(message)
def apply(root):
    targets=(root/DOCK,root/NATIVE,root/VIRTUAL)
    if any(not t.is_file() or t.is_symlink() for t in targets):
        raise ValueError("Missing pinned generated host source")
    before=[t.read_text() for t in targets]
    mods=(patch_dock,patch_native,patch_virtual)
    after=[fn(s) for fn,s in zip(mods,before)]
    if any(fn(s)!=s for fn,s in zip(mods,after)):
        raise ValueError("V103 non-idempotent")
    for t,b,a in zip(targets,before,after):
        if a!=b:t.write_text(a)
    print("[PASS] V103 mode-exclusive guest controls; single tap immediate retained guest switch")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v103_single_guest_control.py <pinned LiveContainer source>")
    apply(Path(sys.argv[1]))
