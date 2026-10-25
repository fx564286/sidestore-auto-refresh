#!/usr/bin/env python3
"""V100 native LiveProcess parity: tap same retained picker, hold explicit actions.

Do not convert Direct mode to LiveProcess or restart running guests.
Long hold offers an explicit Return action, never executes it automatically.
"""
from pathlib import Path
import sys

TARGET=Path("MultitaskSupport/AppSceneViewController.m")
MARK="SCARLET_V100_LIVEPROCESS_MORPH"
OLD_TAP="        self.lcReturnControl.action = ^{ [weakSelf lcReturnToHost]; };"
NEW_TAP="""        // SCARLET_V100_LIVEPROCESS_MORPH: single tap grows the same
        // host-owned recent guest picker as virtual-window mode.
        self.lcReturnControl.action = ^{ [weakSelf lcV76ShowInstalledGuestSwitcher]; };
        // Native press-and-hold offers explicit actions; no direct guest
        // termination or forced app restart is triggered by the gesture.
        self.lcReturnControl.button.showsMenuAsPrimaryAction = NO;
        self.lcReturnControl.button.menu = [UIMenu menuWithChildren:@[
            [UIAction actionWithTitle:@"Return to Scarlet Crystal"
                                image:[UIImage systemImageNamed:@"arrow.uturn.backward"]
                           identifier:nil handler:^(__kindof UIAction *action) {
                [weakSelf lcReturnToHost];
            }],
            [UIAction actionWithTitle:@"Collapse floating control"
                                image:[UIImage systemImageNamed:@"chevron.right"]
                           identifier:nil handler:^(__kindof UIAction *action) {
                [weakSelf.lcReturnControl lcV76CollapseControl];
            }]
        ]];"""
OLD_HOLD="""    [self.button addGestureRecognizer:v76Hold];"""
NEW_HOLD="""    // V100: v76Hold is no longer installed, so native UIButton.menu owns
    // the hold gesture. This avoids firing both guest-picker and native menu.
    v76Hold.enabled = NO;"""

def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or OLD_TAP in s or OLD_HOLD in s:
            raise ValueError("V100 native morph partial")
        return s
    for p in ("LC_GUEST_SWITCH_V76_PATCHED","SCARLET_V87_HOST_GUEST_PICKER"):
        if p not in s: raise ValueError("Missing verified existing native guest context: "+p)
    if s.count(OLD_TAP)!=1 or s.count(OLD_HOLD)!=1:
        raise ValueError("Unexpected native guest control source")
    s=s.replace(OLD_TAP,NEW_TAP,1)
    s=s.replace(OLD_HOLD,NEW_HOLD,1)
    return s

def apply(root):
    p=root/TARGET
    if not p.is_file() or p.is_symlink(): raise ValueError("Missing pinned native guest source")
    before=p.read_text(encoding="utf-8")
    after=patch(before)
    if patch(after)!=after: raise ValueError("V100 native idempotency failed")
    if before!=after:p.write_text(after,encoding="utf-8")
    print("[PASS] V100 LiveProcess single-tap morph + explicit native long-hold actions")

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: patch_v100_native_guest_morph.py <LiveContainer source>")
    apply(Path(sys.argv[1]))
