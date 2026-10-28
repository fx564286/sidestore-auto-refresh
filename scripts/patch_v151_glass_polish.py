#!/usr/bin/env python3
"""V151: round, responsive native glass controls without morph-panel regressions.

Applied after V150; never replaces the host panel, overlay or window.
Reuses UIButton.Configuration.clearGlass() on ALL rows/actions, changes only
their shape/press response, and lets UISegmentedControl own tab gestures.
"""
from pathlib import Path
import sys

DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
MARK="SCARLET_V151_CAPSULE_INTERACTIVE_GLASS"

def once(s,a,b,name):
    n=s.count(a)
    if n!=1:raise ValueError(f"V151 {name}: expected exactly one anchor, got {n}")
    return s.replace(a,b,1)

def patch(s):
    if MARK in s:
        required=["SCARLET_V151_TAB_NATIVE_PRESS", "SCARLET_V151_ROW_PRESS",
                  "SCARLET_V151_PANEL_STATIC_TOUCH", "SCARLET_V150_LONG_PRESS"]
        if s.count(MARK)!=1 or any(x not in s for x in required):
            raise ValueError("V151 capsule patch incomplete")
        return s
    for m in ("SCARLET_V150_INTERACTIVE_CHILD_GLASS","SCARLET_V150_TABS_UNIFIED",
              "SCARLET_V150_GLASS_ROW", "SCARLET_V144_GLASS_INSTALLED",
              '("앱 닫기", "closeWindow")'):
        if m not in s:raise ValueError("V151 missing V150 original: "+m)

    # Current V144 rim tracks the finger but also stretches/moves the
    # ENTIRE native glass panel. On top of V150 button scale this produces
    # the blown-out optical refraction visible in the reported screenshot.
    a='''            // SCARLET_V144_LENS_DRAG: visibly deform the native lens as
            // the finger moves. This is optical geometry, not opacity swap.
            if !UIAccessibility.isReduceMotionEnabled {
                let shiftX = (x - 0.5) * 12.0
                let shiftY = (y - 0.5) * 12.0
                let stretchX = 1.0 + abs(x - 0.5) * 0.038
                let stretchY = 1.0 + abs(y - 0.5) * 0.038
                lens?.transform = CGAffineTransform(
                    translationX: shiftX, y: shiftY)
                    .scaledBy(x: stretchX, y: stretchY)
            }'''
    b='''            // SCARLET_V151_PANEL_STATIC_TOUCH: the parent glass panel
            // stays physically stable; followPoint maintains its living
            // highlight. Only the held CHILD button moves. No double stretch.
            // Never alter lens.transform on a child control's finger input.'''
    s=once(s,a,b,"global panel transform conflict")

    # The system segmented control already has a native, pill-shaped interactive
    # thumb. V150 additionally scaled the entire track on long-press, and a
    # V132 pan recognizer dragged another optical rim over the same segment.
    s=once(s,
        '''            SCGlassControlPress.attach(to: tabPicker)
            NSLog("[SCARLET_V149_TABS] style=system_native extra_lens=0")''',
        '''            // SCARLET_V151_TAB_NATIVE_PRESS: allow UIKit's segmented
            // glass thumb to respond. Do not enlarge the whole tab track.
            NSLog("[SCARLET_V151_TAB_NATIVE_PRESS] native_thumb=1 custom_scale=0")
            NSLog("[SCARLET_V149_TABS] style=system_native extra_lens=0")''',
        "extra segmented long press")

    start=s.index("            let glassTracking = SCNativeGlassFingerTracker(picker: tabPicker, rim: tabRim)")
    end=s.index('            NSLog("[SCARLET_V132_GLASS_DRAG] installed=1 touch_region=tabs")',start)+len('            NSLog("[SCARLET_V132_GLASS_DRAG] installed=1 touch_region=tabs")')
    removed=s[start:end]
    for token in ("UIPanGestureRecognizer", "objc_setAssociatedObject", "tabPicker.addGestureRecognizer"):
        if token not in removed:raise ValueError("V151 tab pan control drift")
    s=s[:start]+'''            // The V132 extra pan recognizer was competing with UIKit
            // native selected-thumb movement, causing duplicated rainbow
            // refraction. Retain the existing static rim and system gestures.
            NSLog("[SCARLET_V151_TAB_NATIVE_PRESS] removed_duplicate_pan=1")'''+s[end:]

    # Native glass button controls must have the SAME capsule shape as tabs,
    # including their accessibility fallback. Do not introduce new glass lens.
    if s.count("cfg.cornerStyle = .large")!=2:
        raise ValueError("V151 recent + Direct capsule anchors drift")
    s=s.replace("cfg.cornerStyle = .large","cfg.cornerStyle = .capsule")
    s=once(s,"config.cornerStyle = .large","config.cornerStyle = .capsule",
           "window actions capsule")

    # Apply the capsule fallback only in V150 rows, not in the panel layout.
    row_old='''                item.configuration = .plain()
                item.backgroundColor = UIColor.secondarySystemGroupedBackground
            }
            SCGlassControlPress.attach(to: item)'''
    row_new='''                item.configuration = .plain()
                item.backgroundColor = UIColor.secondarySystemGroupedBackground
                item.layer.cornerRadius = 23.5
                item.layer.cornerCurve = .continuous
                item.clipsToBounds = true
            }
            // SCARLET_V151_GLASS_ROW: glass button itself
            // owns native interaction; no overlaid rectangle or lens.
            SCGlassControlPress.attach(to: item)'''
    if s.count(row_old)!=2:raise ValueError("V151 fallback row anchor drift")
    s=s.replace(row_old,row_new)

    # A .changed gesture was scheduling a NEW spring animation every
    # finger movement, with huge 10.5% vertical scale and 5pt translation.
    # Animate exactly ONCE on .began, using restrained centered elasticity.
    start=s.index("    @objc private func held(_ gesture: UILongPressGestureRecognizer) {",
                  s.index("private final class SCGlassControlPress"))
    end=s.index("    private func release() {",start)
    old=s[start:end]
    for token in (".scaledBy(x: 1.055, y: 1.105)", "case .began, .changed:", "phase=bulge"):
        if token not in old:raise ValueError("V151 original press mechanism drift")
    new='''    @objc private func held(_ gesture: UILongPressGestureRecognizer) {
        guard let control, control.window != nil else { return }
        switch gesture.state {
        case .began:
            guard !active, !UIAccessibility.isReduceMotionEnabled else { return }
            active = true
            // SCARLET_V151_CAPSULE_INTERACTIVE_GLASS: one press owner.\n            // SCARLET_V151_ROW_PRESS: restrained physical response without
            // sweeping the glass lens, text, or the entire segmented track.
            UIImpactFeedbackGenerator(style: .soft).impactOccurred()
            NSLog("[SCARLET_V150_LONG_PRESS] phase=bulge control=%@",
                  control.accessibilityIdentifier ?? "button")
            NSLog("[SCARLET_V151_ROW_PRESS] phase=pressed scale=1.025")
            UIView.animate(withDuration: 0.16, delay: 0,
                           usingSpringWithDamping: 0.86,
                           initialSpringVelocity: 0,
                           options: [.beginFromCurrentState, .allowUserInteraction],
                           animations: {
                control.transform = CGAffineTransform(scaleX: 1.020, y: 1.025)
            }, completion: nil)
        case .ended, .cancelled, .failed:
            release()
        default:
            // Do NOT animate repeatedly on .changed: that was the bloom bug.
            break
        }
    }

'''
    s=s[:start]+new+s[end:]

    # Release only if an animation was active; protects native immediate taps.
    s=once(s,
        '''        guard let control else { return }
        active = false
        UIView.animate(withDuration: UIAccessibility.isReduceMotionEnabled ? 0 : 0.27,''',
        '''        guard let control, active else { return }
        active = false
        UIView.animate(withDuration: UIAccessibility.isReduceMotionEnabled ? 0 : 0.20,''',
        "press release jitter")

    if s.count("cornerStyle = .capsule")!=3:
        raise ValueError("V151 missing 3 capsule button row types")
    if 'SCGlassControlPress.attach(to: tabPicker)' in s:
        raise ValueError("V151 still enlarges the entire segmented control")
    return s

def apply(root):
    file=root/DOCK
    if not file.is_file() or file.is_symlink():raise ValueError("canonical V150 dock source missing")
    old=file.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:raise ValueError("V151 patch not idempotent")
    if old!=new:file.write_text(new,encoding="utf-8")
    print("[PASS] V151 capsule rows, native tab thumb, low-bloom press and stable parent panel")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v151_glass_polish.py <LiveContainer>")
    apply(Path(sys.argv[1]))
