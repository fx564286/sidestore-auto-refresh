#!/usr/bin/env python3
"""V153: recent-row clipping, outside-touch dismiss, Direct shared picker.
Apply strictly AFTER V152; parent glass panel and tabs are untouched.
"""
from pathlib import Path
import sys
DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
SHELL=Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
MARK="SCARLET_V153_THREE_ISSUE_FIX"

def one(src,a,b,key):
    n=src.count(a)
    if n!=1:raise ValueError(f"V153 {key} expected 1 anchor; got {n}")
    return src.replace(a,b,1)

def dock(s):
    if MARK in s:
        if s.count(MARK)!=1 or any(x not in s for x in
           ("SCARLET_V153_RECENT_UNCLIPPED","SCARLET_V153_OUTSIDE_TOUCH_BEGIN",
            "SCARLET_V153_DIRECT_ROOT_SAFE")):raise ValueError("partial V153 dock")
        return s
    for x in ("SCARLET_V151_CAPSULE_INTERACTIVE_GLASS","SCARLET_V150_OUTSIDE_TOUCH_DOWN",
              "SCARLET_V151_TAB_NATIVE_PRESS",'("앱 닫기", "closeWindow")'):
        if x not in s:raise ValueError("V153 expects V152 "+x)
    s=one(s,
'''        let scroll = UIScrollView()
        scroll.showsVerticalScrollIndicator = !windowActions && recent.count > 5''',
'''        let scroll = UIScrollView()
        // SCARLET_V153_THREE_ISSUE_FIX:
        // SCARLET_V153_RECENT_UNCLIPPED: keep the native clear-glass
        // capsule highlight visible outside its scroll viewport without
        // changing the parent glass panel or native segmented tabs.
        scroll.clipsToBounds = windowActions || directMode
        scroll.showsVerticalScrollIndicator = !windowActions && recent.count > 5''',
        "recent optical clipping")
    # Keep existing row widths 100% unchanged, especially the already-correct
    # window-action tab. The scroll clipping policy changes only for recents.
    s=one(s,
'''            scroll.showsVerticalScrollIndicator = !windowActions && recent.count > 5
            let count = directMode ? 2''',
'''            scroll.showsVerticalScrollIndicator = !windowActions && recent.count > 5
            scroll.clipsToBounds = windowActions || directMode
            let count = directMode ? 2''',
        "clip only recent app rows on tab switch")
    start=s.index('''        } else if !windowActions {
        for guest in recent {''')
    end=s.index('''        } else {
            // Same native system-material panel as recents.''',start)
    block=s[start:end]
    if block.count("SCGlassControlPress.attach(to: item)")!=1:raise ValueError("recent row press anchor")
    block=block.replace("SCGlassControlPress.attach(to: item)",
       '''// Native clearGlass owns recent row press response. Avoid
            // a second UIView scale that clipped optical edges in scroll.
            NSLog("[SCARLET_V153_RECENT_UNCLIPPED] press=native_glass capsule=1")''')
    s=s[:start]+block+s[end:]

    s=one(s,"    private weak var primaryTap: UITapGestureRecognizer?",
             "    private weak var primaryTap: SCOutsideTouchDownRecognizer?",
             "outside gesture property")
    s=one(s,
'''    func install(with primary: UITapGestureRecognizer) {
        primaryTap = primary
        refreshWindows()''',
'''    func install(with primary: SCOutsideTouchDownRecognizer) {
        // SCARLET_V153_OUTSIDE_TOUCH_BEGIN: listen at first contact on the
        // existing overlay AND all active UIWindow hit-test surfaces.
        primaryTap = primary
        if let overlay = panel?.superview {
            primary.cancelsTouchesInView = false
            primary.delaysTouchesBegan = false
            primary.delegate = self
            primary.addTarget(self, action: #selector(outsideTouch(_:)))
            overlay.addGestureRecognizer(primary)
            installed.append(primary)
        }
        refreshWindows()''',
        "overlay touch-down install")
    s=one(s,
'''            // Existing owner window still uses its original empty-overlay
            // touchDown action. Guest windows need their own first-touch hook.
            guard let gesture: UIGestureRecognizer = window === owner
                    ? primaryTap : SCOutsideTouchDownRecognizer() else { continue }''',
'''            // Also monitor owner and guest windows: all use touchBegan.
            // dismissQueued prevents duplicate animation and touch steals.
            let gesture: UIGestureRecognizer = SCOutsideTouchDownRecognizer()''',
        "window touch down monitor")
    s=one(s,"        let outsideTap = UITapGestureRecognizer()",
             "        let outsideTap = SCOutsideTouchDownRecognizer()",
             "replace tap on up")

    s=one(s,
'''        sourceView.isHidden = true
        UIAccessibility.post(notification: .layoutChanged, argument: heading)''',
'''        // SCARLET_V153_DIRECT_ROOT_SAFE: a deep-link host anchor is
        // root.view, never hide that whole host scene as a 'button'.
        if sourceView !== controller.view &&
           sourceView !== owner.rootViewController?.view {
            sourceView.isHidden = true
        } else {
            NSLog("[SCARLET_V153_DIRECT] host_anchor_visible=1")
        }
        UIAccessibility.post(notification: .layoutChanged, argument: heading)''',
        "Direct host root hide")
    return s

def shell(s):
    mark="SCARLET_V153_DIRECT_HOST_PICKER"
    if mark in s:
        if s.count(mark)!=1:raise ValueError("duplicate Direct host route")
        return s
    if "SCARLET_V147_DIRECT_HOST_ROUTING" not in s:raise ValueError("V147 host route missing")
    # Direct host activation can lag the return deep-link by more than 0.6s.
    # Keep bounded attempts; no new polling thread/window/button.
    s=one(s,"            for delay in [0.0, 0.22, 0.60] {",
             "            for delay in [0.0, 0.22, 0.60, 1.20, 2.0] {",
             "Direct foreground handoff timing")
    return one(s,
'''                        MultitaskDockManager.shared.nrgV72PresentGuestSwitcher(
                            from: root, sourceView: root.view)
                        NSLog("[SCARLET_V147_DIRECT] route=host result=presented")''',
'''                        // SCARLET_V153_DIRECT_HOST_PICKER: preserve the
                        // ONE host picker, but use its Direct-mode entry point.
                        MultitaskDockManager.shared.nrgV112PresentDirectGuestUI(
                            from: root, sourceView: root.view)
                        NSLog("[SCARLET_V147_DIRECT] route=host result=presented")
                        NSLog("[SCARLET_V153_DIRECT] route=host mode=direct picker=invoked")''',
        "Direct routed picker")

def apply(root):
    entries=[]
    for path,fn in ((DOCK,dock),(SHELL,shell)):
        f=root/path
        if not f.is_file() or f.is_symlink():raise ValueError("missing "+str(f))
        old=f.read_text(encoding="utf-8");new=fn(old)
        if fn(new)!=new:raise ValueError("V153 patch not idempotent")
        entries.append((f,old,new))
    for f,old,new in entries:
        if old!=new:f.write_text(new,encoding="utf-8")
    print("[PASS] V153 recent press, outside touch-down, Direct original picker")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v153_three_fixes.py <LC>")
    apply(Path(sys.argv[1]))
