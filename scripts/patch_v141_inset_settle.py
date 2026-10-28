#!/usr/bin/env python3
"""V141: safe-area bounded fullscreen view hit testing."""
from pathlib import Path
import sys

DECO=Path('MultitaskSupport/DecoratedAppSceneViewController.m')
DELEGATE=Path('LiveContainerSwiftUI/App/AppDelegate.swift')

def replace_one(s,old,new,why):
    n=s.count(old)
    if n!=1:raise ValueError(f'V141 {why}: expected exactly one pinned anchor, got {n}')
    return s.replace(old,new,1)


def decorated(s):
    marker='SCARLET_V141_INSET_AWARE_SETTLE'
    if marker in s:
        if s.count(marker)!=1 or 'nrgV141LastWindowInsets' not in s:
            raise ValueError('partial V141 viewport frame state')
        return s
    if 'SCARLET_V136_ROTATION_ATOMIC' not in s or 'SCARLET_V129_VIEWPORT' not in s:
        raise ValueError('V141 portrait touch frame source missing')
    s=replace_one(s,
        '''@property(nonatomic) UIInterfaceOrientation nrgV55LastHostOrientation;''',
        '''@property(nonatomic) UIInterfaceOrientation nrgV55LastHostOrientation;
// SCARLET_V141_INSET_AWARE_SETTLE: orientation+size alone cannot detect
// safe-area stabilization or a post-rotation origin mismatch.
@property(nonatomic) UIEdgeInsets nrgV141LastWindowInsets;
@property(nonatomic) CGRect nrgV141LastViewportFrame;''',
        'per-controller window inset and physical-frame cache')
    s=replace_one(s,
        '''    if (CGSizeEqualToSize(self.nrgV55LastHostSize, size) &&
        self.nrgV55LastHostOrientation == orientation && !guestIsStale) return;
    self.nrgV55LastHostSize = size;
    self.nrgV55LastHostOrientation = orientation;''',
        '''    // V141: the host can keep the same width/height while UIKit
    // applies a different Dynamic Island inset; position is not size.
    BOOL insetChanged = !UIEdgeInsetsEqualToEdgeInsets(
        self.nrgV141LastWindowInsets, window.safeAreaInsets);
    CGRect viewportFrame = [self.view.superview convertRect:self.view.frame toView:window];
    BOOL viewportChanged = !CGRectEqualToRect(viewportFrame, self.nrgV141LastViewportFrame);
    if (CGSizeEqualToSize(self.nrgV55LastHostSize, size) &&
        self.nrgV55LastHostOrientation == orientation && !guestIsStale &&
        !insetChanged && !viewportChanged) return;
    self.nrgV55LastHostSize = size;
    self.nrgV55LastHostOrientation = orientation;
    self.nrgV141LastWindowInsets = window.safeAreaInsets;
    self.nrgV141LastViewportFrame = viewportFrame;''',
        'do not reuse stale frame based solely on width and height')
    s=replace_one(s,
        '''    [self.appSceneVC.view setNeedsLayout];
    NSLog(@"[SCARLET_V136_ROTATION] phase=commit''',
        '''    [self.appSceneVC.view setNeedsLayout];
    self.nrgV141LastViewportFrame = [self.view.superview convertRect:self.view.frame toView:window];
    NSLog(@"[SCARLET_V141_ROTATION] phase=viewport_commit insetTop=%.1f viewY=%.1f touchY=%.1f",
          window.safeAreaInsets.top, self.view.frame.origin.y,
          self.nrgV141LastViewportFrame.origin.y);
    NSLog(@"[SCARLET_V136_ROTATION] phase=commit''',
        'record actual post-commit touch position')
    return s


def delegate(s):
    mark='SCARLET_V141_ROTATION_SAFEAREA_SETTLE'
    if mark in s:
        if s.count(mark)!=1:raise ValueError('duplicate V141 rotation callback')
        return s
    if 'SCARLET_V136_ROTATION_SETTLE' not in s:
        raise ValueError('V141 requires bounded V136 reconciliation')
    s=replace_one(s,
        '''            DispatchQueue.main.asyncAfter(deadline: .now() + 0.28) { [weak windowScene] in
                guard let windowScene else { return }
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }''',
        '''            DispatchQueue.main.asyncAfter(deadline: .now() + 0.28) { [weak windowScene] in
                guard let windowScene else { return }
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }
            // SCARLET_V141_ROTATION_SAFEAREA_SETTLE: iOS 27 often settles
            // top safe-area AFTER UIWindow width/height have stabilized.
            // Two final bounded checks, never a repeating timer.
            for delay in [0.55, 0.95] {
                DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak windowScene] in
                    guard let windowScene, windowScene.activationState == .foregroundActive else { return }
                    MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
                }
            }''',
        'one additional safe-area stabilization phase')
    return s


def apply(root:Path):
    edits=[]
    for rel,fn in ((DECO,decorated),(DELEGATE,delegate)):
        p=root/rel
        if not p.is_file() or p.is_symlink():raise ValueError('missing pinned source '+str(rel))
        old=p.read_text();new=fn(old)
        if fn(new)!=new:raise ValueError('V141 settle patch non-idempotent')
        edits.append((p,old,new))
    for p,old,new in edits:
        if old!=new:p.write_text(new)
    print('[PASS] V141 frame-origin/inset stable after rotation')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v141_inset_settle.py <LiveContainer>')
    apply(Path(sys.argv[1]))
