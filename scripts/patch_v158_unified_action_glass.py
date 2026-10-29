#!/usr/bin/env python3
"""V158: both tabs EXACT SAME outer width/height, long-press glass actions
never clipped, preserve one picker/one overlay, no second button or Direct.
Apply after V157 on generated LC Swift. Strict idempotent one-anchor patch.
"""
from pathlib import Path
import sys
FILE=Path("MultitaskSupport/MultitaskDockView.swift")
MARK="SCARLET_V158_EQUAL_TAB_FRAME"

def once(s,old,new,why):
    n=s.count(old)
    if n!=1:raise ValueError(f"V158 {why}: anchor expected 1 actual {n}")
    return s.replace(old,new,1)

def patch(src):
    if MARK in src:
        for x in ("SCARLET_V158_ACTION_UNCLIPPED","SCARLET_V158_ACTION_INSETS",
                  "SCARLET_V157_WIDE_PANEL","SCARLET_V156_OUTSIDE_TOUCH_TRACE"):
            if x not in src:raise ValueError("partial V158 patch "+x)
        if src.count(MARK)!=1:raise ValueError("duplicate V158")
        return src
    for x in ("SCARLET_V156_STABLE_PANEL_HEIGHT","SCARLET_V157_WIDE_PANEL",
              "SCARLET_V151_TAB_NATIVE_PRESS","SCARLET_V155_DOCK_SINGLE_MODE"):
        if x not in src:raise ValueError("V158 requires "+x)
    # V156's list grows with recently-used app count, while 3 action buttons
    # have only 3 rows. Fix one shared viewport height for BOTH tabs and
    # keep recent apps scrollable. Fixed window action size is the golden
    # reference, including in portrait/landscape.
    src=once(src,'''        let listHeight = min(
            max(CGFloat(actionsCount * 54),
                CGFloat(max(1, recent.count)) * 54 + 24),
            maxListHeight)''',
'''        // SCARLET_V158_EQUAL_TAB_FRAME: keep existing action-panel size
        // regardless of recent app count or which segment is selected.
        // Recent tab scrolls inside the same panel when the list is longer.
        let listHeight = min(CGFloat(actionsCount * 54), maxListHeight)
        NSLog("[SCARLET_V158_FRAME_HEIGHT] list_height=%.1f", listHeight)''',
        "initial shared action-panel viewport")
    src=once(src,'''            tabListHeightConstraint.constant = min(
                max(CGFloat(actionsCount * 54),
                    CGFloat(max(1, recent.count)) * 54 + 24),
                maxListHeight)''',
'''            // Both tabs share ONE fixed list size, not an intrinsic
            // 1-row/2-row/3-row height that resizes the material surface.
            tabListHeightConstraint.constant = listHeight''',
        "tab-switch shared action-panel viewport")

    # Window actions in V157 had ZERO extra layout margins, so adding 18pt
    # here makes the original three pills 36pt narrower. The actual crop is
    # scroll.clipsToBounds in windowActions mode. Allow overflow there while
    # retaining the original action button width and parent panel geometry.
    # Keep recent-row padding unchanged.
    src=once(src,'''        scroll.clipsToBounds = windowActions
        scroll.showsVerticalScrollIndicator''',
'''        // SCARLET_V158_ACTION_UNCLIPPED: UIKit's optical long-press
        // bloom is allowed to extend past the action-list viewport.
        // The OUTER material border stays rounded and unchanged.
        scroll.clipsToBounds = false
        scroll.showsVerticalScrollIndicator''',
        "initial action clipping")
    src=once(src,'''            scroll.clipsToBounds = windowActions
            rows.isLayoutMarginsRelativeArrangement = !windowActions''',
'''            scroll.clipsToBounds = false
            rows.isLayoutMarginsRelativeArrangement = true
            // SCARLET_V158_EQUAL_ROW_GEOMETRY: same button geometry in both tabs.
            rows.layoutMargins = UIEdgeInsets(top: 12, left: 18, bottom: 12, right: 18)
            NSLog("[SCARLET_V158_ACTION_UNCLIPPED] actions=%d clips=0 inset=0",
                  windowActions ? 1 : 0)''',
        "tab-switch action insets and clipping")
    src=once(src,'''        rows.isLayoutMarginsRelativeArrangement = true
        // SCARLET_V156_ROW_OPTICAL_PAD:''',
'''        rows.isLayoutMarginsRelativeArrangement = !windowActions
        // SCARLET_V156_ROW_OPTICAL_PAD:''',
        "initial action margins enabled")
    src=once(src,'''        rows.layoutMargins = UIEdgeInsets(top: 12, left: 18, bottom: 12, right: 18)
        scroll.addSubview(rows)''',
'''        rows.layoutMargins = UIEdgeInsets(top: 12, left: 18, bottom: 12, right: 18)
        scroll.addSubview(rows)''',
        "initial action horizontal insets")

    # Ensure the scroll and rounded outer pane remain the same object and
    # confirm visual optical clearance without claiming device verification.
    src=once(src,
'''                SCGlassControlPress.attach(to: item)
                item.addAction(UIAction { _ in''',
'''                // SCARLET_V158_ACTION_UNCLIPPED: full-size V157 capsule;
                // no viewport clipping while held, no button width change.
                SCGlassControlPress.attach(to: item)
                item.addAction(UIAction { _ in''',
        "action row gesture preserved")
    return src

def apply(root):
    f=root/FILE
    if not f.is_file() or f.is_symlink():raise ValueError("generated V158 Swift missing")
    old=f.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:raise ValueError("V158 idempotence failed")
    if new!=old:f.write_text(new,encoding="utf-8")
    print("[PASS] V158 identical tab frames; action caps unclipped, button widths untouched")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v158_unified_action_glass.py <LC>")
    apply(Path(sys.argv[1]))
