#!/usr/bin/env python3
"""V147: rebuild from last successful V144, not the V145/V146 patch stack.

One canonical panel. Restore app-close semantics, apply native interactive
glass to panel tabs and all action/guest buttons, and dismiss on outside taps
across currently visible windows in the owner's scene. No new UIWindow.
"""
from pathlib import Path
import sys

FILE = Path("MultitaskSupport/MultitaskDockView.swift")
MARK = "SCARLET_V147_FROM_V144_GLASS_OWNER"

def once(s, old, new, label):
    hits=s.count(old)
    if hits!=1: raise ValueError(f"V147 {label}: required 1 exact source, got {hits}")
    return s.replace(old,new,1)

def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or s.count('"scarlet.v147.row.glass"')!=3:
            raise ValueError("V147 partial or duplicate implementation")
        return s
    for prereq in ("SCARLET_V144_WINDOW_OUTSIDE_TAP","SCARLET_V144_GLASS_INSTALLED",
                   "SCARLET_V141_OUTSIDE_TAP_DISMISS","SCARLET_V139_PANEL_TOUCH"):
        if prereq not in s: raise ValueError("V147 V144 baseline missing "+prereq)

    s=once(s,'("창 닫기", "closeWindow")','("앱 닫기", "closeWindow")',
           "restore guest termination label while keeping closeWindow selector")

    # Parent panel remains the ONE clear native lens. V145's opaque .regular
    # parent glass is deliberately NOT inherited.
    s=once(s,
        'NSLog("[SCARLET_V144_GLASS_INSTALLED] lens=native_clear border=continuous")',
        '''// SCARLET_V147_FROM_V144_GLASS_OWNER: preserve V144's clear
        // interactive native lens, with consistent glass on controls.
        NSLog("[SCARLET_V144_GLASS_INSTALLED] lens=native_clear border=continuous")
        NSLog("[SCARLET_V147_GLASS] panel=clear tabs=native rows=native")''',
        "glass evidence")

    s=once(s,
        '''            tabPicker.backgroundColor = UIColor.white.withAlphaComponent(0.12)
            tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.48)''',
        '''            // Native glass is a subview of the EXISTING tab housing.
            // It does not receive touches; the existing segmented control
            // remains the only tab-switch owner.
            let tabsEffect = UIGlassEffect(style: .regular)
            tabsEffect.isInteractive = true
            let tabsLens = UIVisualEffectView(effect: tabsEffect)
            tabsLens.isUserInteractionEnabled = false
            tabsLens.clipsToBounds = true
            tabsLens.layer.cornerRadius = 20
            tabsLens.layer.cornerCurve = .continuous
            tabsLens.translatesAutoresizingMaskIntoConstraints = false
            tabHousing.insertSubview(tabsLens, at: 0)
            NSLayoutConstraint.activate([
                tabsLens.leadingAnchor.constraint(equalTo: tabHousing.leadingAnchor),
                tabsLens.trailingAnchor.constraint(equalTo: tabHousing.trailingAnchor),
                tabsLens.topAnchor.constraint(equalTo: tabHousing.topAnchor),
                tabsLens.bottomAnchor.constraint(equalTo: tabHousing.bottomAnchor)
            ])
            tabPicker.backgroundColor = .clear
            tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.12)''',
        "native tab glass")

    # Two rows are indented 12 spaces (Direct + recent), and window actions
    # one level deeper. V147 patches all three, not just the panel.
    old='''                item.backgroundColor = UIColor.secondarySystemBackground.withAlphaComponent(0.56)
                item.layer.borderColor = UIColor.separator.withAlphaComponent(0.42).cgColor
                item.layer.borderWidth = 0.55
                item.layer.cornerCurve = .continuous'''
    repl='''                item.backgroundColor = .clear
                item.layer.borderColor = UIColor.white.withAlphaComponent(0.25).cgColor
                item.layer.borderWidth = 0.5
                item.layer.cornerCurve = .continuous
                let rowEffect = UIGlassEffect(style: .regular)
                rowEffect.isInteractive = true
                let rowLens = UIVisualEffectView(effect: rowEffect)
                rowLens.accessibilityIdentifier = "scarlet.v147.row.glass"
                rowLens.isUserInteractionEnabled = false
                rowLens.clipsToBounds = true
                rowLens.layer.cornerRadius = 15
                rowLens.layer.cornerCurve = .continuous
                rowLens.translatesAutoresizingMaskIntoConstraints = false
                item.insertSubview(rowLens, at: 0)
                NSLayoutConstraint.activate([
                    rowLens.leadingAnchor.constraint(equalTo: item.leadingAnchor),
                    rowLens.trailingAnchor.constraint(equalTo: item.trailingAnchor),
                    rowLens.topAnchor.constraint(equalTo: item.topAnchor),
                    rowLens.bottomAnchor.constraint(equalTo: item.bottomAnchor)
                ])'''
    if s.count(old)!=2:raise ValueError("V147 direct/recent glass rows mismatch")
    s=s.replace(old,repl)
    deeper_old="\n".join("    "+line for line in old.split("\n"))
    deeper_repl="\n".join("    "+line for line in repl.split("\n"))
    s=once(s,deeper_old,deeper_repl,"window action native glass")

    # V144's owner-window recognizer misses touches delivered to a guest
    # UIWindow re-ordered above the picker. Reuse the observer and keep
    # exactly one panel, but install one recognizer per visible scene window.
    s=once(s,
        '''    var dismiss: (() -> Void)?

    init(owner: UIWindow, panel: UIView, dismiss: @escaping () -> Void) {''',
        '''    var dismiss: (() -> Void)?
    private var installed: [UITapGestureRecognizer] = []

    init(owner: UIWindow, panel: UIView, dismiss: @escaping () -> Void) {''',
        "observer storage")

    s=once(s,
        '''    func gestureRecognizer(_ recognizer: UIGestureRecognizer,
                           shouldReceive touch: UITouch) -> Bool {''',
        '''    func install(with primary: UITapGestureRecognizer) {
        guard let owner, let scene = owner.windowScene else { return }
        var windows = scene.windows.filter {
            !$0.isHidden && $0.alpha > 0.01 && $0.isUserInteractionEnabled
        }
        if !windows.contains(where: { $0 === owner }) { windows.append(owner) }
        for window in windows {
            let tap = window === owner ? primary : UITapGestureRecognizer()
            tap.cancelsTouchesInView = true
            tap.delaysTouchesBegan = false
            tap.delegate = self
            tap.addTarget(self, action: #selector(outsideTap(_:)))
            window.addGestureRecognizer(tap)
            installed.append(tap)
        }
        NSLog("[SCARLET_V147_OUTSIDE] monitors=%ld", installed.count)
    }

    func uninstall() {
        for tap in installed {
            tap.view?.removeGestureRecognizer(tap)
            tap.delegate = nil
            tap.removeTarget(self, action: #selector(outsideTap(_:)))
        }
        installed.removeAll()
    }

    func gestureRecognizer(_ recognizer: UIGestureRecognizer,
                           shouldReceive touch: UITouch) -> Bool {''',
        "all windows in one scene")

    s=once(s,
        '''        guard let owner, let panel, panel.window === owner else { return false }
        return !panel.convert(panel.bounds, to: owner).contains(touch.location(in: owner))''',
        '''        guard let owner, let panel, panel.window === owner,
              let touchedWindow = touch.window,
              touchedWindow.windowScene === owner.windowScene else { return false }
        return !panel.bounds.contains(touch.location(in: panel))''',
        "ignore touches inside glass panel")

    s=once(s,
        '''        if panel.convert(panel.bounds, to: owner).contains(recognizer.location(in: owner)) {
            return
        }''',
        '''        if panel.bounds.contains(recognizer.location(in: panel)) {
            return
        }''',
        "cross window panel conversion")

    s=once(s,
        '''            if let outsideTap { owner?.removeGestureRecognizer(outsideTap) }''',
        '''            if let backdrop = overlay,
               let observer = objc_getAssociatedObject(backdrop,
                   UnsafeRawPointer(bitPattern: 0x144)!) as? SCOutsideGlassTapObserver {
                observer.uninstall()
                objc_setAssociatedObject(backdrop,
                   UnsafeRawPointer(bitPattern: 0x144)!,
                   nil, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
            }''',
        "remove all scene gesture monitors on dismiss")

    s=once(s,
        '''        outsideTap.addTarget(outsideObserver,
            action: #selector(SCOutsideGlassTapObserver.outsideTap(_:)))
        outsideTap.delegate = outsideObserver''',
        '''        outsideObserver.install(with: outsideTap)''',
        "connect existing outside observer")

    s=once(s,
        '''        owner.addGestureRecognizer(outsideTap)
        NSLog("[SCARLET_V144_PICKER] outside_guard=window_attached")''',
        '''        NSLog("[SCARLET_V144_PICKER] outside_guard=window_attached")''',
        "no extra owner recognizer")

    return s

def apply(root):
    p=root/FILE
    if not p.is_file() or p.is_symlink():raise ValueError("V147 missing pinned canonical picker")
    original=p.read_text(encoding="utf-8")
    result=patch(original)
    if patch(result)!=result:raise ValueError("V147 UI not idempotent")
    if original!=result:p.write_text(result,encoding="utf-8")
    print("[PASS] V147: V144 panel, three true-native glass row types, app close, outside scene taps")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v147_from_v144.py <LiveContainer>")
    apply(Path(sys.argv[1]))
