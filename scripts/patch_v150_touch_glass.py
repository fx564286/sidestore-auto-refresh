#!/usr/bin/env python3
"""V150: press-responsive child controls and reliable scene/window outside-touch.

Strictly preserves the full V149 panel geometry, UIGlassEffect, morph animation,
UIWindow/overlay creation, routes and bundle identity. Edits only the existing
touch observer, tabs and button styling. Idempotent, reject unexpected baseline.
"""
from pathlib import Path
import sys

PATH=Path("MultitaskSupport/MultitaskDockView.swift")
MARK="SCARLET_V150_INTERACTIVE_CHILD_GLASS"

def one(src, a, b, reason):
    if src.count(a) != 1:
        raise ValueError(f"{reason} source anchor drift: {src.count(a)} matches")
    return src.replace(a,b,1)

def patch(src):
    if MARK in src:
        checks=("SCARLET_V150_OUTSIDE_TOUCH_DOWN",
                "SCARLET_V150_LONG_PRESS",
                "SCARLET_V150_GLASS_ROW",
                "SCARLET_V150_TABS_UNIFIED")
        if src.count(MARK)!=1 or any(x not in src for x in checks):
            raise ValueError("partial/duplicate V150")
        return src
    checks=("SCARLET_V149_DYNAMIC_OUTSIDE","SCARLET_V149_TABS",
            "SCARLET_V148_ACTION_GLASS_NATIVE_OWNER",
            '("앱 닫기", "closeWindow")')
    for x in checks:
        if x not in src: raise ValueError("V150 requires V149: "+x)

    # Non-exclusive immediate recognizer, attached to CURRENT foreground
    # app windows, not another overlay or newly created UIWindow.
    observer_start=src.index("private final class SCOutsideGlassTapObserver:")
    observer_end=src.index("// SCARLET_V139_PANEL_TOUCH:",observer_start)
    old=src[observer_start:observer_end]
    required=("private var installed: [UITapGestureRecognizer]",
              "panel.window === owner",
              "window.windowScene === owner.windowScene",
              "func install(with primary: UITapGestureRecognizer)",
              "func uninstall()",
              "@objc func outsideTap(_ recognizer: UITapGestureRecognizer)")
    if any(x not in old for x in required):
        raise ValueError("V150 observer contract unexpected")
    new=StringObserver
    src=src[:observer_start]+new+src[observer_end:]

    # Common button press response. The native glass button stays the sole
    # hit target; a non-cancelling long-press recognizer only animates itself.
    anchor="// SCARLET_V139_PANEL_TOUCH:"
    src=one(src,anchor,PressClass+anchor,"glass press animator")

    # Tab selected capsule must not be opaque, unlike regular system tint.
    src=one(src,
        '''            tabPicker.backgroundColor = .clear
            NSLog("[SCARLET_V149_TABS] style=system_native extra_lens=0")''',
        '''            // SCARLET_V150_TABS_UNIFIED: selected capsule matches the
            // CLEAR glass buttons instead of an opaque white card.
            tabPicker.backgroundColor = .clear
            tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.18)
            tabPicker.setTitleTextAttributes([.foregroundColor: UIColor.label],
                                             for: .normal)
            tabPicker.setTitleTextAttributes([.foregroundColor: UIColor.label],
                                             for: .selected)
            SCGlassControlPress.attach(to: tabPicker)
            NSLog("[SCARLET_V149_TABS] style=system_native extra_lens=0")
            NSLog("[SCARLET_V150_TABS_UNIFIED] tint=translucent native_selection=1")''',
        "tabs selected tint")

    # Two pre-V149 row variants have identical background/border decoration,
    # V149 native action rows already have clearGlass. Bring all three types
    # to the same system-material style, without changing action closures.
    oldstyle='''            item.layer.cornerRadius = 15
            if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
                // The panel owns Liquid Glass; rows remain translucent controls.
                item.configuration = .glass()
                item.backgroundColor = .clear
                item.layer.borderColor = UIColor.white.withAlphaComponent(0.25).cgColor
                item.layer.borderWidth = 0.5
                item.layer.cornerCurve = .continuous
                // Native Liquid Glass is owned by UIButton.Configuration.glass()
                // and responds to touch; do NOT put a separate static
                // UIVisualEffectView behind a plain UIButton.
            } else {
                item.backgroundColor = UIColor.secondarySystemGroupedBackground
            }'''
    if src.count(oldstyle)!=2:
        raise ValueError(f"V150 expected 2 prior row styles, got {src.count(oldstyle)}")
    src=src.replace(oldstyle,'''            // SCARLET_V150_GLASS_ROW: recent/restart rows are the SAME
            // clear material as window actions (no gray or white border).
            if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
                var cfg = UIButton.Configuration.clearGlass()
                cfg.baseForegroundColor = .label
                cfg.cornerStyle = .large
                item.configuration = cfg
            } else {
                item.configuration = .plain()
                item.backgroundColor = UIColor.secondarySystemGroupedBackground
            }
            SCGlassControlPress.attach(to: item)''')

    # UIKit configuration may overwrite UIButton.setTitle or deprecated
    # titleEdgeInsets, use the configuration's directional content inset.
    src=one(src,
        '''            item.titleEdgeInsets = UIEdgeInsets(top: 0, left: 13, bottom: 0, right: 12)''',
        '''            if var cfg = item.configuration {
                cfg.contentInsets = NSDirectionalEdgeInsets(top: 0, leading: 14,
                                                              bottom: 0, trailing: 12)
                item.configuration = cfg
            }''',"recent row padding")

    # UIButton.Configuration can override legacy setTitle state. Set both
    # sources so real iOS 26+ clearGlass rows never lose their labels.
    src=one(src,
        '''            item.setTitle("재시작 후 Scarlet Crystal로 복귀", for: .normal)''',
        '''            item.setTitle("재시작 후 Scarlet Crystal로 복귀", for: .normal)
            if var cfg = item.configuration {
                cfg.title = "재시작 후 Scarlet Crystal로 복귀"
                item.configuration = cfg
            }''', "direct glass config title")
    src=one(src,
        '''            item.setTitle((guest.running ? "●  " : "◌  ") + guest.name, for: .normal)''',
        '''            let rowTitle = (guest.running ? "●  " : "◌  ") + guest.name
            item.setTitle(rowTitle, for: .normal)
            if var cfg = item.configuration {
                cfg.title = rowTitle
                cfg.titleAlignment = .leading
                item.configuration = cfg
            }''', "recent glass config title")

    # Window actions use same press behavior, attached before row action.
    src=one(src,
        '''                item.heightAnchor.constraint(equalToConstant: 47).isActive = true
                item.addAction(UIAction { _ in
                    collapse {''',
        '''                item.heightAnchor.constraint(equalToConstant: 47).isActive = true
                SCGlassControlPress.attach(to: item)
                item.addAction(UIAction { _ in
                    collapse {''',"action press binding")

    # A recent-app selection removes the overlay immediately instead of
    # running collapse. Its attached window listeners must be removed too.
    # Otherwise old recognizers survive and steal/duplicate future taps.
    src=one(src,
        '''                let dismissSelection: () -> Void = {
                    overlay.removeFromSuperview()
                    sourceView.isHidden = false
                }''',
        '''                let dismissSelection: () -> Void = {
                    if let observer = objc_getAssociatedObject(overlay,
                        UnsafeRawPointer(bitPattern: 0x144)!) as? SCOutsideGlassTapObserver {
                        observer.uninstall()
                        objc_setAssociatedObject(overlay,
                            UnsafeRawPointer(bitPattern: 0x144)!, nil,
                            .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
                    }
                    overlay.removeFromSuperview()
                    sourceView.isHidden = false
                }''',
        "recent app selection outside gesture cleanup")

    # Latest controller retains previous source-wide glass and layout.
    if src.count("SCGlassControlPress.attach(to: item)") != 3:
        raise ValueError("V150 not attached to all 3 button types")
    if "SCARLET_V150_OUTSIDE_TOUCH_DOWN" not in src:
        raise ValueError("V150 outside path missing")
    return src

StringObserver='''// SCARLET_V150_OUTSIDE_TOUCH_DOWN: respond at finger-down, not after a
// failed tap competition with the guest's scroll/video recognizers.
// Non-exclusive; the existing child button and the guest keep their touches.
private final class SCOutsideTouchDownRecognizer: UIGestureRecognizer {
    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent) {
        super.touchesBegan(touches, with: event)
        state = .began
    }
    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent) {
        super.touchesMoved(touches, with: event)
        if state == .began { state = .changed }
    }
    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent) {
        super.touchesEnded(touches, with: event)
        if state == .began || state == .changed { state = .ended }
    }
    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent) {
        super.touchesCancelled(touches, with: event)
        state = .cancelled
    }
}

private final class SCOutsideGlassTapObserver: NSObject, UIGestureRecognizerDelegate {
    weak var owner: UIWindow?
    weak var panel: UIView?
    var dismiss: (() -> Void)?
    private var installed: [UIGestureRecognizer] = []
    private weak var primaryTap: UITapGestureRecognizer?
    private var windowTokens: [NSObjectProtocol] = []
    private var dismissQueued = false

    init(owner: UIWindow, panel: UIView, dismiss: @escaping () -> Void) {
        self.owner = owner
        self.panel = panel
        self.dismiss = dismiss
        super.init()
    }

    // V150 keeps V149's scene monitoring but additionally detects guest
    // windows belonging to a separate foreground UIWindowScene on this screen.
    // SCARLET_V149_CONTROLS_ONLY: original V144 panel stays unchanged.
    // SCARLET_V149_DYNAMIC_OUTSIDE: existing windows; never create a new one.
    func install(with primary: UITapGestureRecognizer) {
        primaryTap = primary
        refreshWindows()
        for name in [UIWindow.didBecomeVisibleNotification,
                     UIWindow.didBecomeKeyNotification] {
            let token = NotificationCenter.default.addObserver(
                forName: name, object: nil, queue: .main) { [weak self] note in
                guard let self, let window = note.object as? UIWindow,
                      let owner = self.owner,
                      window.screen === owner.screen else { return }
                self.refreshWindows()
            }
            windowTokens.append(token)
        }
    }

    private func refreshWindows() {
        guard let owner, let panel, panel.window === owner else { return }
        let windows = UIApplication.shared.connectedScenes.compactMap {
            $0 as? UIWindowScene
        }.filter {
            $0.screen === owner.screen &&
            ($0.activationState == .foregroundActive ||
             $0.activationState == .foregroundInactive)
        }.flatMap { $0.windows }.filter {
            !$0.isHidden && $0.alpha > 0.01 && $0.isUserInteractionEnabled
        }
        for window in windows {
            if installed.contains(where: { $0.view === window }) { continue }
            // Existing owner window still uses its original empty-overlay
            // touchDown action. Guest windows need their own first-touch hook.
            guard let gesture: UIGestureRecognizer = window === owner
                    ? primaryTap : SCOutsideTouchDownRecognizer() else { continue }
            gesture.cancelsTouchesInView = false
            gesture.delaysTouchesBegan = false
            gesture.delegate = self
            gesture.addTarget(self, action: #selector(outsideTouch(_:)))
            window.addGestureRecognizer(gesture)
            installed.append(gesture)
            NSLog("[SCARLET_V150_OUTSIDE] attached level=%.1f window=%@",
                  window.windowLevel.rawValue, window)
        }
        NSLog("[SCARLET_V149_OUTSIDE] scene_monitor_count=%ld", installed.count)
        NSLog("[SCARLET_V150_OUTSIDE] monitored=%ld", installed.count)
    }

    func uninstall() {
        for token in windowTokens { NotificationCenter.default.removeObserver(token) }
        windowTokens.removeAll()
        for gesture in installed {
            gesture.view?.removeGestureRecognizer(gesture)
            gesture.delegate = nil
            gesture.removeTarget(self, action: #selector(outsideTouch(_:)))
        }
        installed.removeAll()
        primaryTap = nil
        dismissQueued = false
    }

    private func outsidePanel(_ touch: UITouch) -> Bool {
        guard let owner, let panel, panel.window === owner,
              let window = touch.window,
              window.screen === owner.screen else { return false }
        // Normalize both windows to screen coordinates. The prior
        // touch.location(in: panel) across different guest scenes could
        // misclassify an outside touch as inside.
        let onScreen = window.convert(touch.location(in: window), to: owner.screen.coordinateSpace)
        let panelOnScreen = owner.convert(panel.convert(panel.bounds, to: owner), to: owner.screen.coordinateSpace)
        return !panelOnScreen.contains(onScreen)
    }

    func gestureRecognizer(_ recognizer: UIGestureRecognizer,
                           shouldReceive touch: UITouch) -> Bool {
        outsidePanel(touch)
    }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
      shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool {
        true
    }

    @objc private func outsideTouch(_ gesture: UIGestureRecognizer) {
        let immediate = gesture is SCOutsideTouchDownRecognizer
        guard !dismissQueued,
              (immediate ? gesture.state == .began : gesture.state == .ended),
              owner != nil, panel?.window === owner else { return }
        dismissQueued = true
        NSLog("[SCARLET_V150_OUTSIDE] phase=touch_down owner=%d",
              immediate ? 0 : 1)
        // Removal of the hosting recognizer on the current callback stack
        // must not invalidate the in-flight touch. Collapse next run loop.
        DispatchQueue.main.async { [weak self] in
            guard let self else { return }
            self.dismiss?()
        }
    }
}

'''

PressClass='''// SCARLET_V150_INTERACTIVE_CHILD_GLASS: a finger-local elastic bloom on
// the ORIGINAL UIKit control. No additional view, window or overlay is made.
// A .24s press grows gently; release springs back without consuming action.
private final class SCGlassControlPress: NSObject, UIGestureRecognizerDelegate {
    private weak var control: UIControl?
    private var active = false

    private init(_ control: UIControl) {
        self.control = control
        super.init()
    }

    static func attach(to control: UIControl) {
        let animator = SCGlassControlPress(control)
        let hold = UILongPressGestureRecognizer(
            target: animator, action: #selector(animator.held(_:)))
        hold.minimumPressDuration = 0.24
        hold.allowableMovement = 26
        hold.cancelsTouchesInView = false
        hold.delaysTouchesBegan = false
        hold.delegate = animator
        control.addGestureRecognizer(hold)
        objc_setAssociatedObject(control, UnsafeRawPointer(bitPattern: 0x150)!,
            animator, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
    }

    @objc private func held(_ gesture: UILongPressGestureRecognizer) {
        guard let control, control.window != nil else { return }
        switch gesture.state {
        case .began, .changed:
            guard !UIAccessibility.isReduceMotionEnabled else { return }
            let p = gesture.location(in: control)
            let x = min(1, max(0, p.x / max(1, control.bounds.width)))
            let y = min(1, max(0, p.y / max(1, control.bounds.height)))
            let dx = (x - 0.5) * 5.0
            let dy = (y - 0.5) * 3.0
            let grow = CGAffineTransform(translationX: dx, y: dy)
                .scaledBy(x: 1.055, y: 1.105)
            if !active {
                active = true
                UIImpactFeedbackGenerator(style: .soft).impactOccurred()
                NSLog("[SCARLET_V150_LONG_PRESS] phase=bulge control=%@",
                      control.accessibilityIdentifier ?? "tabs")
            }
            UIView.animate(withDuration: 0.20, delay: 0,
                usingSpringWithDamping: 0.65, initialSpringVelocity: 0.4,
                options: [.beginFromCurrentState, .allowUserInteraction],
                animations: { control.transform = grow }, completion: nil)
        case .ended, .cancelled, .failed:
            release()
        default: break
        }
    }

    private func release() {
        guard let control else { return }
        active = false
        UIView.animate(withDuration: UIAccessibility.isReduceMotionEnabled ? 0 : 0.27,
            delay: 0, usingSpringWithDamping: 0.72,
            initialSpringVelocity: 0,
            options: [.beginFromCurrentState, .allowUserInteraction],
            animations: { control.transform = .identity }, completion: nil)
        NSLog("[SCARLET_V150_LONG_PRESS] phase=release")
    }

    func gestureRecognizer(_ recognizer: UIGestureRecognizer,
       shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool {
        true
    }
}

'''

def apply(root):
    p=root/PATH
    if not p.is_file() or p.is_symlink():raise ValueError("canonical dock source missing")
    old=p.read_text()
    new=patch(old)
    if patch(new)!=new: raise ValueError("V150 non-idempotent")
    if old!=new:p.write_text(new)
    print("[PASS] V150 existing panel immutable, elastic child glass and scene-aware outside touches")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v150_touch_glass.py <LiveContainer>")
    apply(Path(sys.argv[1]))
