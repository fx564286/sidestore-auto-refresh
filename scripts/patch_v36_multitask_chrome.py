#!/usr/bin/env python3
"""Keep virtual multitasking; remove maximized window chrome and respect safe area."""
from pathlib import Path
import sys
MARKER='NRG_V36_MAXIMIZED_GUEST_CHROME'
TARGET='MultitaskSupport/DecoratedAppSceneViewController.m'
def patch(source):
    if MARKER in source: return source
    old='BOOL hideWindowBar = MultitaskDockManager.shared.isCollapsed && self.isMaximized;'
    new='// '+MARKER+': no host title bar over maximized guest; dock remains available.\n        BOOL hideWindowBar = self.isMaximized;'
    if source.count(old)!=1: raise ValueError('chrome anchor mismatch')
    source=source.replace(old,new,1)
    return source
if __name__=='__main__':
    p=Path(sys.argv[1])/TARGET;s=p.read_text();t=patch(s)
    if s!=t:p.write_text(t)
    print('[PASS] V36 maximized guest chrome removed; virtual multitasking retained')
