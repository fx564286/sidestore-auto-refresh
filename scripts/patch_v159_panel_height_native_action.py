#!/usr/bin/env python3
"""V159: preserve native V158 outer panel width/height across tab changes,
and prevent custom UIView scaling from clipping ACTION button clearGlass.
Applies strictly after V158. No additional panel, glass, button or Direct.
"""
from pathlib import Path
import sys

DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
MARK="SCARLET_V159_PINNED_OUTER_FRAME"

def change(s,a,b,key):
    if s.count(a)!=1:
        raise ValueError(f"V159 {key} anchor drift: {s.count(a)}")
    return s.replace(a,b,1)

def patch(s):
    if MARK in s:
        for marker in ("SCARLET_V159_ACTION_NATIVE_PRESS","SCARLET_V159_PANEL_EQUAL"):
            if marker not in s:raise ValueError("V159 partial patch "+marker)
        if s.count(MARK)!=1:raise ValueError("V159 duplicate")
        return s
    for marker in ("SCARLET_V158_EQUAL_TAB_FRAME","SCARLET_V158_ACTION_UNCLIPPED",
                   "SCARLET_V157_WIDE_PANEL","SCARLET_V156_OUTSIDE_TOUCH_TRACE"):
        if marker not in s:raise ValueError("V159 missing V158 source "+marker)
    # Pin to the golden initial frame rather than relying on the UIStackView's
    # content re-measuring after a recent-list / window-actions tab switch.
    # Width, height, location, native clear glass and the outside overlay stay.
    s=change(s,
'''        owner.layoutIfNeeded()
        overlay.layoutIfNeeded()
        owner.bringSubviewToFront(overlay)''',
'''        owner.layoutIfNeeded()
        overlay.layoutIfNeeded()
        // SCARLET_V159_PINNED_OUTER_FRAME: freeze the already-laid-out
        // WINDOW-ACTION-SIZED native panel after the single initial layout.
        // The underlying scroll content can change, but the outer pane can't.
        stablePanelHeight = material.bounds.height
        guard stablePanelHeight > 0 else {
            NSLog("[SCARLET_V159_PANEL_EQUAL] geometry=invalid height=%.1f", stablePanelHeight)
            return
        }
        let frozenHeight = material.heightAnchor.constraint(equalToConstant: stablePanelHeight)
        frozenHeight.priority = .required
        frozenHeight.isActive = true
        NSLog("[SCARLET_V159_PANEL_EQUAL] height=%.1f width=%.1f mode=%d",
              stablePanelHeight, material.bounds.width, windowActions ? 1 : 0)
        owner.bringSubviewToFront(overlay)''',
        "freeze initial native panel frame")
    # The callback is declared before the first presentation layout. Keep
    # a local capture that is assigned after layout, not a forward let ref.
    s=change(s,
        """        tabPicker.addAction(UIAction { [weak self, weak tabPicker, weak overlay, weak tabHousing] _ in""",
        """        var stablePanelHeight: CGFloat = 0
        tabPicker.addAction(UIAction { [weak self, weak tabPicker, weak overlay, weak tabHousing] _ in""",
        "stable height capture before UIAction closure")
    # On every tab switch, assert there is zero size drift. No new layout
    # constraints; failures are observable without losing the current panel.
    s=change(s,
'''            UIAccessibility.post(notification: .layoutChanged, argument: heading)
            NSLog("[SCARLET_V126_TAB] mode=%@ direct=%d overlay_retained=1",''',
'''            if abs(material.bounds.height - stablePanelHeight) > 0.5 {
                NSLog("[SCARLET_V159_PANEL_EQUAL] unexpected_layout_drift=%.2f",
                      material.bounds.height - stablePanelHeight)
                overlay.layoutIfNeeded()
            }
            UIAccessibility.post(notification: .layoutChanged, argument: heading)
            NSLog("[SCARLET_V126_TAB] mode=%@ direct=%d overlay_retained=1",''',
        "tab frame regression trace")
    # capture material & stable height in tab closure explicitly; Swift
    # captures material by default because used, stableHeight is let.
    # The native UIButton.Configuration.clearGlass has its OWN press
    # animation. Scaling the entire UIButton also scales/masks the system's
    # optical surface, causing apparent cut-off on action rows specifically.
    # Keep recognizer/haptic; never transform the native action UIButton.
    s=change(s,
'''    private weak var control: UIControl?
    private var active = false

    private init(_ control: UIControl) {
        self.control = control''',
'''    private weak var control: UIControl?
    private var active = false
    private let nativeOnly: Bool

    private init(_ control: UIControl, nativeOnly: Bool = false) {
        self.nativeOnly = nativeOnly
        self.control = control''',
        "optical native mode")
    s=change(s,
'''    static func attach(to control: UIControl) {
        let animator = SCGlassControlPress(control)''',
'''    static func attach(to control: UIControl, nativeOnly: Bool = false) {
        let animator = SCGlassControlPress(control, nativeOnly: nativeOnly)''',
        "optical press attachment")
    s=change(s,
'''            UIImpactFeedbackGenerator(style: .soft).impactOccurred()
            NSLog("[SCARLET_V150_LONG_PRESS] phase=bulge control=%@",''',
'''            UIImpactFeedbackGenerator(style: .soft).impactOccurred()
            if nativeOnly {
                // SCARLET_V159_ACTION_NATIVE_PRESS: native clearGlass
                // manages its own elastic press and optical border.
                NSLog("[SCARLET_V159_ACTION_NATIVE_PRESS] phase=began transform=identity")
                return
            }
            NSLog("[SCARLET_V150_LONG_PRESS] phase=bulge control=%@",''',
        "preserve native press on long hold")
    s=change(s,
'''        active = false
        UIView.animate(withDuration: UIAccessibility.isReduceMotionEnabled ? 0 : 0.20,''',
'''        active = false
        if nativeOnly {
            NSLog("[SCARLET_V159_ACTION_NATIVE_PRESS] phase=released transform=identity")
            return
        }
        UIView.animate(withDuration: UIAccessibility.isReduceMotionEnabled ? 0 : 0.20,''',
        "skip secondary transform on release")
    s=change(s,
'''                // SCARLET_V158_ACTION_UNCLIPPED: same elastic press, but
                // now has 18pt inner clearance and no scroll clipping.
                SCGlassControlPress.attach(to: item)''',
'''                // SCARLET_V158_ACTION_UNCLIPPED: native clearGlass has
                // 18pt horizontal optical clearance and no scroll clipping.
                // SCARLET_V159_ACTION_NATIVE_PRESS: do NOT scale UIView;
                // UIKit's own glass press responds without clipped optics.
                SCGlassControlPress.attach(to: item, nativeOnly: true)''',
        "action-row native glass press")
    return s

def apply(root):
    f=root/DOCK
    if not f.is_file() or f.is_symlink(): raise ValueError("V159 Dock missing")
    old=f.read_text()
    new=patch(old)
    if patch(new)!=new:raise ValueError("V159 not idempotent")
    if old!=new:f.write_text(new)
    print("[PASS] V159 stable external frame and non-scaling native action longpress")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v159_panel_height_native_action.py <LC>")
    apply(Path(sys.argv[1]))
