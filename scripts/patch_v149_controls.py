#!/usr/bin/env python3
"""V149: focused UI controls and outside-touch repair atop successful V148.

STRICT: the already-good parent panel, geometry, rim, animations, and
finger tracker are immutable. Only native tab styling, right action button
configuration and existing outside gesture monitor are altered.
"""
from pathlib import Path
import sys

DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
MARK="SCARLET_V149_CONTROLS_ONLY"

def replace_exact(s, old, new, label):
    n=s.count(old)
    if n!=1:raise ValueError(f"V149 {label}: expected one anchor, found {n}")
    return s.replace(old,new,1)

def patch(s):
    if MARK in s:
        for required in ("SCARLET_V149_TABS", "SCARLET_V149_ACTION_GLASS",
                         "SCARLET_V149_DYNAMIC_OUTSIDE", "windowTokens.removeAll()"):
            if required not in s:raise ValueError("V149 partial patch: "+required)
        if s.count(MARK)!=1:raise ValueError("V149 duplicate patch")
        return s

    for required in ("SCARLET_V148_ACTION_GLASS_NATIVE_OWNER",
                     "SCARLET_V147_FROM_V144_GLASS_OWNER",
                     "SCARLET_V144_WINDOW_OUTSIDE_TAP",
                     '("앱 닫기", "closeWindow")',
                     "바깥을 누르면 창 관리 닫기"):
        if required not in s:raise ValueError("V149 expected V148 baseline: "+required)

    # Keep the native UISegmentedControl as the SOLE tab input owner.
    # V147 had inserted ANOTHER .regular glass sampler under it, then
    # cleared its stock background image. That negated native tab visuals.
    t0=s.index("            // Native glass is a subview of the EXISTING tab housing.")
    t1=s.index("            let glassTracking = SCNativeGlassFingerTracker",t0)
    tabs=s[t0:t1]
    for required in ("tabsLens = UIVisualEffectView(effect: tabsEffect)",
                     "tabPicker.setBackgroundImage(UIImage()", "selectedSegmentTintColor"):
        if required not in tabs:raise ValueError("V149 missing previous tab override "+required)
    s=s[:t0]+"""            // SCARLET_V149_TABS: allow the iOS 26+ system segmented control
            // to render and interact using its actual native appearance.
            // Never layer a second opaque glass sampler behind these tabs.
            tabPicker.backgroundColor = .clear
            NSLog("[SCARLET_V149_TABS] style=system_native extra_lens=0")
"""+s[t1:]

    # This is a button configuration change, not a panel visual change.
    s=replace_exact(s,
        "var config = UIButton.Configuration.glass()",
        """// SCARLET_V149_ACTION_GLASS: a clear interactive system glass
                    // button, rather than a gray regular-glass capsule.
                    var config = UIButton.Configuration.clearGlass()""",
        "right window-action glass")
    s=replace_exact(s,
        'NSLog("[SCARLET_V148_ACTION_GLASS] action=%@ owner=UIButton style=glass", selectorName)',
        '''NSLog("[SCARLET_V148_ACTION_GLASS] action=%@ owner=UIButton style=glass", selectorName)
                    NSLog("[SCARLET_V149_ACTION_GLASS] action=%@ style=clearGlass reduceTransparency=0", selectorName)''',
        "right button runtime evidence")
    s=replace_exact(s,
        '''                    item.backgroundColor = UIColor.secondarySystemGroupedBackground
                    item.setTitle(title, for: .normal)''',
        '''                    item.backgroundColor = UIColor.secondarySystemGroupedBackground
                    NSLog("[SCARLET_V149_ACTION_GLASS] action=%@ style=accessibility_fallback reduceTransparency=%d",
                          selectorName, UIAccessibility.isReduceTransparencyEnabled ? 1 : 0)
                    item.setTitle(title, for: .normal)''',
        "accessibility fallback evidence")

    # Maintain the original host panel and UIWindow. Merely reattach the
    # existing observer to guest windows appearing AFTER presentation.
    c0=s.index("    func install(with primary: UITapGestureRecognizer) {")
    c1=s.index("    func gestureRecognizer(_ recognizer: UIGestureRecognizer,",c0)
    observer=s[c0:c1]
    for required in ("scene.windows.filter", "installed.removeAll()", "tap.addTarget(self"):
        if required not in observer:raise ValueError("V149 missing V147 observer "+required)

    s=replace_exact(s,
        "    private var installed: [UITapGestureRecognizer] = []",
        """    private var installed: [UITapGestureRecognizer] = []
    private weak var primaryTap: UITapGestureRecognizer?
    private var windowTokens: [NSObjectProtocol] = []""",
        "observer lifecycle storage")
    c0=s.index("    func install(with primary: UITapGestureRecognizer) {")
    c1=s.index("    func gestureRecognizer(_ recognizer: UIGestureRecognizer,",c0)
    s=s[:c0]+"""    // SCARLET_V149_CONTROLS_ONLY: existing panel is unchanged.
    // SCARLET_V149_DYNAMIC_OUTSIDE: no new window, panel, or button.
    // Watch only windows in the ORIGINAL owner's scene and refresh when
    // UIKit inserts or reorders a Direct/LiveProcess guest UIWindow.
    func install(with primary: UITapGestureRecognizer) {
        primaryTap = primary
        refreshWindows()
        for name in [UIWindow.didBecomeVisibleNotification,
                     UIWindow.didBecomeKeyNotification] {
            let token = NotificationCenter.default.addObserver(
                forName: name, object: nil, queue: .main) { [weak self] note in
                guard let self, let window = note.object as? UIWindow,
                      let owner = self.owner,
                      window.windowScene === owner.windowScene else { return }
                self.refreshWindows()
            }
            windowTokens.append(token)
        }
    }

    private func refreshWindows() {
        guard let owner, let scene = owner.windowScene,
              let panel, panel.window === owner else { return }
        var windows = scene.windows.filter {
            !$0.isHidden && $0.alpha > 0.01 && $0.isUserInteractionEnabled
        }
        if !windows.contains(where: { $0 === owner }) { windows.append(owner) }
        for window in windows {
            if installed.contains(where: { $0.view === window }) { continue }
            guard let tap = window === owner ? primaryTap : UITapGestureRecognizer() else { continue }
            tap.cancelsTouchesInView = true
            tap.delaysTouchesBegan = false
            tap.delegate = self
            tap.addTarget(self, action: #selector(outsideTap(_:)))
            window.addGestureRecognizer(tap)
            installed.append(tap)
            NSLog("[SCARLET_V149_OUTSIDE] monitor_attached level=%.1f",
                  window.windowLevel.rawValue)
        }
        NSLog("[SCARLET_V149_OUTSIDE] scene_monitor_count=%ld", installed.count)
    }

    func uninstall() {
        for token in windowTokens { NotificationCenter.default.removeObserver(token) }
        windowTokens.removeAll()
        for tap in installed {
            tap.view?.removeGestureRecognizer(tap)
            tap.delegate = nil
            tap.removeTarget(self, action: #selector(outsideTap(_:)))
        }
        installed.removeAll()
        primaryTap = nil
    }

"""+s[c1:]

    # This marker also lets CI prove the parent glass is still V144/V148
    # untouched. The new code must stay outside its panel construction.
    if "SCARLET_V149_CONTROLS_ONLY" not in s:raise ValueError("V149 marker missing")
    if '("창 닫기", "closeWindow")' in s:raise ValueError("V149 app-close wording regression")
    return s

def apply(root):
    p=root/DOCK
    if not p.is_file() or p.is_symlink():raise ValueError("V149 canonical dock missing")
    old=p.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:raise ValueError("V149 not idempotent")
    if new!=old:p.write_text(new,encoding="utf-8")
    print("[PASS] V149 native segmented tabs, clearGlass actions, dynamic outside observer; parent panel unchanged")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v149_controls.py <LiveContainer>")
    apply(Path(sys.argv[1]))
