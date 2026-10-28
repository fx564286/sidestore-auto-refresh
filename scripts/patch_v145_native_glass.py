#!/usr/bin/env python3
"""V145: native adaptive glass, cross-window modal dismissal, and safe window actions.

Runs after V144's canonical one-panel renderer. Reuses the existing UIControls;
no extra window, floating handle, credentials, or guest process changes.
"""
from pathlib import Path
import sys

DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
MARK = "SCARLET_V145_NATIVE_GLASS_AND_DISMISS"

OBSERVER = """// SCARLET_V144_WINDOW_OUTSIDE_TAP: retain one canonical picker and owner.
// SCARLET_V145_NATIVE_GLASS_AND_DISMISS: observe all foreground windows in
// this UIWindowScene, because touches in a higher guest UIWindow are never
// delivered to a gesture recognizer on the lower host UIWindow.
private final class SCOutsideGlassTapObserver: NSObject, UIGestureRecognizerDelegate {
    weak var owner: UIWindow?
    weak var panel: UIView?
    var dismiss: (() -> Void)?
    private var monitors: [UITapGestureRecognizer] = []

    init(owner: UIWindow, panel: UIView, dismiss: @escaping () -> Void) {
        self.owner = owner
        self.panel = panel
        self.dismiss = dismiss
        super.init()
    }

    func install(using first: UITapGestureRecognizer) {
        guard let owner, let scene = owner.windowScene else { return }
        // No new UIWindow: attach a recognizer only to already visible
        // windows of this same scene. Never monitor another scene.
        var windows = scene.windows.filter {
            !$0.isHidden && $0.alpha > 0.01 && $0.isUserInteractionEnabled
        }
        if !windows.contains(where: { $0 === owner }) { windows.append(owner) }
        for window in windows {
            let tap = window === owner ? first : UITapGestureRecognizer()
            tap.cancelsTouchesInView = true
            tap.delaysTouchesBegan = false
            tap.delegate = self
            tap.addTarget(self, action: #selector(outsideTap(_:)))
            window.addGestureRecognizer(tap)
            monitors.append(tap)
        }
        NSLog("[SCARLET_V145_PICKER] monitors=%ld scene=foreground", monitors.count)
    }

    func uninstall() {
        for tap in monitors {
            tap.view?.removeGestureRecognizer(tap)
            tap.delegate = nil
            tap.removeTarget(self, action: #selector(outsideTap(_:)))
        }
        monitors.removeAll()
    }

    func gestureRecognizer(_ recognizer: UIGestureRecognizer,
                           shouldReceive touch: UITouch) -> Bool {
        guard let owner, let panel, panel.window === owner,
              let touchedWindow = touch.window,
              touchedWindow.windowScene === owner.windowScene else { return false }
        return !panel.bounds.contains(touch.location(in: panel))
    }

    @objc func outsideTap(_ recognizer: UITapGestureRecognizer) {
        guard recognizer.state == .ended,
              let owner, let panel, panel.window === owner else { return }
        if panel.bounds.contains(recognizer.location(in: panel)) { return }
        NSLog("[SCARLET_V144_PICKER] dismissed=window_outside_tap")
        NSLog("[SCARLET_V145_PICKER] reason=outside_across_scene_window")
        dismiss?()
    }
}

"""

def once(s, a, b, why):
    n=s.count(a)
    if n!=1: raise ValueError(f"V145 {why}: expected one anchor, found {n}")
    return s.replace(a,b,1)

def transform(s):
    if MARK in s:
        if s.count(MARK)!=1 or "monitors.removeAll()" not in s or "outsideObserver.install(using: outsideTap)" not in s:
            raise ValueError("V145 incomplete or duplicate panel")
        return s
    for required in ("SCARLET_V144_WINDOW_OUTSIDE_TAP",
                     "SCARLET_V144_GLASS_INSTALLED",
                     "SCARLET_V141_OUTSIDE_TAP_DISMISS",
                     "SCARLET_V129_PICKER_RESILIENCE"):
        if required not in s:
            raise ValueError("V145 missing predecessor: " + required)
    start=s.index("// SCARLET_V144_WINDOW_OUTSIDE_TAP:")
    end=s.index("// SCARLET_V139_PANEL_TOUCH:",start)
    if s[start:end].count("class SCOutsideGlassTapObserver")!=1:
        raise ValueError("V145 noncanonical outside observer")
    s=s[:start]+OBSERVER+s[end:]
    s=once(s, "let steadyGlass = UIGlassEffect(style: .clear)",
           "// SCARLET_V145 system regular glass: stronger native refraction from first presentation.\n            let steadyGlass = UIGlassEffect(style: .regular)",
           "use system adaptive glass instead of nearly invisible clear")
    s=once(s, "material.layer.borderWidth = 1.0",
           "material.layer.borderWidth = 0.65",
           "reduce artificial white panel border")
    s=once(s, "material.layer.borderColor = UIColor.white.withAlphaComponent(0.62).cgColor",
           "material.layer.borderColor = UIColor.white.withAlphaComponent(0.42).cgColor",
           "native edge instead of white frame")
    s=once(s,
           "if let outsideTap { owner?.removeGestureRecognizer(outsideTap) }",
           """if let backdrop = overlay,
               let observer = objc_getAssociatedObject(backdrop,
                   UnsafeRawPointer(bitPattern: 0x144)!) as? SCOutsideGlassTapObserver {
                observer.uninstall()
                objc_setAssociatedObject(backdrop, UnsafeRawPointer(bitPattern: 0x144)!,
                    nil, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
            }""",
           "remove each window recognizer on dismissal")
    s=once(s,
           """outsideTap.addTarget(outsideObserver,
            action: #selector(SCOutsideGlassTapObserver.outsideTap(_:)))
        outsideTap.delegate = outsideObserver""",
           "outsideObserver.install(using: outsideTap)",
           "observe all scene windows once")
    s=once(s,
           "        owner.addGestureRecognizer(outsideTap)\n        NSLog(\"[SCARLET_V144_PICKER] outside_guard=window_attached\")",
           "        NSLog(\"[SCARLET_V144_PICKER] outside_guard=window_attached\")",
           "remove single-window-only handler")
    s=once(s,
           "let actionsCount = 4 // V129: three window controls + per-app viewport switch.",
           "let actionsCount = 3 // V145: only three clear window actions.",
           "remove confusing action row count")
    s=once(s,
           '("창 닫기", "closeWindow"),\n                ("화면 표시 방식 전환", "nrgV129ToggleViewportMode")',
           '("창 닫기", "closeWindow")',
           "retire viewport debug control from user-facing menu")
    return s

def apply(root):
    p=root/DOCK
    if not p.is_file() or p.is_symlink():
        raise ValueError("V145 missing canonical renderer")
    original=p.read_text(encoding="utf-8")
    patched=transform(original)
    if transform(patched)!=patched:
        raise ValueError("V145 not idempotent")
    if patched!=original:p.write_text(patched,encoding="utf-8")
    print("[PASS] V145 native adaptive glass, multi-UIWindow dismissal, three window actions")

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: patch_v145_native_glass.py <LiveContainer>")
    apply(Path(sys.argv[1]))
