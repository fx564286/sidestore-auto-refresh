#!/usr/bin/env python3
"""V141: restore dismissal from empty screen with one host picker.

A V140 clear backdrop defers UIControl.touchUpInside when touch starts or ends
outside a stable hit region. Use touchDown on the existing full-window UIControl
only, never attach a second UIWindow, recognizer, screen, or control to guest.
"""
from pathlib import Path
import sys
SOURCE=Path('MultitaskSupport/MultitaskDockView.swift')
MARK='SCARLET_V141_OUTSIDE_TAP_DISMISS'

def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or '.touchDown)' not in s:raise ValueError('partial V141 outside dismissal')
        return s
    for pre in ('SCARLET_V140_MORPH_ANCHOR', 'SCARLET_V139_PANEL_TOUCH',
                'scarlet.v100.morph.backdrop'):
        if pre not in s:raise ValueError('V141 missing common picker '+pre)
    before='''        overlay.addAction(UIAction { _ in collapse({}) }, for: .touchUpInside)'''
    after='''        // SCARLET_V141_OUTSIDE_TAP_DISMISS: the existing full-window
        // UIControl owns empty-space touches. touchUpInside could be lost
        // when overlay alpha/geometry changes during the spring transition.
        // Child UIControls handle their own input, so touching a panel row
        // does NOT close it. No second overlay or recognizer is introduced.
        overlay.addAction(UIAction { _ in
            NSLog("[SCARLET_V141_PICKER] dismiss=outside_tap")
            collapse({})
        }, for: .touchDown)'''
    n=s.count(before)
    if n!=1:raise ValueError(f'V141 missing sole outside action: {n}')
    s=s.replace(before,after,1)
    # Place backdrop above the host content after child views have been
    # mounted. It is still an existing UIWindow child; no new root/window.
    before='''        owner.layoutIfNeeded()
        overlay.layoutIfNeeded()
        NSLog("[SCARLET_V140_GLASS]'''
    after='''        owner.layoutIfNeeded()
        overlay.layoutIfNeeded()
        owner.bringSubviewToFront(overlay)
        NSLog("[SCARLET_V140_GLASS]'''
    n=s.count(before)
    if n!=1:raise ValueError(f'V141 expected existing V140 presentation commit: {n}')
    return s.replace(before,after,1)

def apply(root):
    path=root/SOURCE
    if not path.is_file() or path.is_symlink():raise ValueError('missing pinned dock source')
    old=path.read_text(encoding='utf-8');new=patch(old)
    if patch(new)!=new:raise ValueError('V141 outside tap non-idempotent')
    if new!=old:path.write_text(new,encoding='utf-8')
    print('[PASS] V141 common picker outside tap closes on first touch-down')
if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v141_outside_tap.py <LiveContainer>')
    apply(Path(sys.argv[1]))
