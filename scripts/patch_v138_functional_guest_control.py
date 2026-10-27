#!/usr/bin/env python3
"""V138: restore functional host V73 picker as the only LiveProcess control.

V137 removed the functional host native V73 control and left a guest-process
SCGuestMorphWindow, whose Direct picker bridge is not available in isolated
LiveProcess guest processes. Host controllers cannot be looked up directly
across process boundaries. Keep V73 on hosted virtual windows; instantiate
SCGuestMorphWindow only for Direct, never both on the same guest. No signing,
JIT, original containers, or user data changes.
"""
from pathlib import Path
import sys

BOOT = Path('LiveContainer/LCBootstrap.m')
WINDOW = Path('MultitaskSupport/DecoratedAppSceneViewController.m')
DOCK = Path('MultitaskSupport/MultitaskDockView.swift')
MARK = 'SCARLET_V138_FUNCTIONAL_OWNER'


def one(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f'V138 {label}: expected one anchor, observed {count}')
    return source.replace(old, new, 1)


def boot(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or 'if (!isLiveProcess && !isSideStore) {' not in source:
            raise ValueError('V138 invalid Direct-only bootstrap guard')
        return source
    if 'SCARLET_V137_SCENE_OWNER' not in source or 'SCARLET_V105_DIRECT_UNIFIED_MORPH' not in source:
        raise ValueError('V138 missing audited legacy bootstrap scene owner')
    if 'SCARLET_V137_UNIFIED_GUEST_ENTRY' in source:
        raise ValueError('V138 must never use the nonfunctional V137 guest-process sole owner')
    # V105 originally instantiated its fallback for every guest, including
    # LiveProcess. In V138 the actual hosted V73 provides a working button.
    source = one(source,
        'if (!isSideStore) {',
        '''// SCARLET_V138_FUNCTIONAL_OWNER: virtual LiveProcess uses native V73
        // to reach the live host window manager; Direct uses shared fallback.
        if (!isLiveProcess && !isSideStore) {''',
        'Direct-only fallback ownership')
    # In Direct, the Swift host framework might not be loaded in the guest.
    # Prefer its existing common picker, otherwise open the host on user tap,
    # rather than leave a visible button permanently inert.
    source = one(source,
        '''    NSLog(@"[SCARLET_V114_UI] common_router_unavailable=1 framework_loaded=0");''',
        '''    NSLog(@"[SCARLET_V138_ACTION] common_router_unavailable=1 fallback=host_link");
    NSURL *returnURL = [NSURL URLWithString:@"scarletcrystal251://"];
    if (returnURL) {
        [UIApplication.sharedApplication openURL:returnURL options:@{}
            completionHandler:^(BOOL accepted) {
                NSLog(@"[SCARLET_V138_ACTION] fallback=host_link accepted=%d", accepted);
            }];
    }''',
        'Direct button must offer a real host navigation fallback')
    return source


def window(source: str) -> str:
    if 'SCARLET_V137_UNIFIED_GUEST_ENTRY' in source:
        raise ValueError('V138 wrong virtual owner: V73 removed')
    for marker in ('SCARLET_V103_VIRTUAL_ONLY_CONTROL', 'nrgV100TapMorph:',
                   'NRG_V73_APPLE_FLOATING_CONTROL', 'SCARLET_V136_ROTATION_ATOMIC'):
        if marker not in source:
            raise ValueError('V138 functional native V73 owner missing: ' + marker)
    if source.count('scarlet.v103.virtual.guest.control') != 1:
        raise ValueError('V138 expected exactly one native hosted guest handle')
    return source


def dock(source: str) -> str:
    for marker in ('SCARLET_V112_SHARED_GUEST_UI',
                   '@objc(SCUnifiedGuestUIBridge)',
                   'nrgV72PresentGuestSwitcher(from: controller, sourceView: sourceView)'):
        if marker not in source:
            raise ValueError('V138 existing functional host picker missing ' + marker)
    return source


def apply(root: Path) -> None:
    edits = []
    for rel, fn in ((BOOT, boot), (WINDOW, window), (DOCK, dock)):
        file = root / rel
        if not file.is_file() or file.is_symlink():
            raise ValueError('V138 missing or unsafe source ' + str(rel))
        original = file.read_text(encoding='utf-8')
        patched = fn(original)
        if fn(patched) != patched:
            raise ValueError('V138 non-idempotent ' + str(rel))
        edits.append((file, original, patched))
    for file, original, patched in edits:
        if original != patched:
            file.write_text(patched, encoding='utf-8')
    print('[PASS] V138 functional V73 host owner; Direct-only fallback; no two same-mode buttons')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: patch_v138_functional_guest_control.py <pinned LiveContainer root>')
    apply(Path(sys.argv[1]))
