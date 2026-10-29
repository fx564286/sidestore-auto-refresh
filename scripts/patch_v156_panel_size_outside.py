#!/usr/bin/env python3
"""V156 preserve window-management-sized glass panel for both tabs and
fix outside tap routing diagnostics, keeping one native picker and one overlay.

Applies after V155 on the generated LC source, strict/idempotent.
"""
from pathlib import Path
import sys

FILE=Path("MultitaskSupport/MultitaskDockView.swift")
MARK="SCARLET_V156_STABLE_PANEL_HEIGHT"

def one(src,a,b,name):
    n=src.count(a)
    if n!=1:raise ValueError(f"V156 {name}: expected 1 anchor, got {n}")
    return src.replace(a,b,1)

def patch(src):
    if MARK in src:
        for x in ("SCARLET_V156_OUTSIDE_TOUCH_TRACE","SCARLET_V156_ROW_OPTICAL_PAD","SCARLET_V155_DOCK_SINGLE_MODE"):
            if x not in src:raise ValueError("V156 incomplete "+x)
        return src
    for needle in ("SCARLET_V155_RECENT_OPTICAL_HEIGHT","SCARLET_V155_OUTSIDE_HITTEST",
                   "SCARLET_V155_DOCK_SINGLE_MODE","SCARLET_V154_OUTSIDE_BACKDROP"):
        if needle not in src:raise ValueError("V156 prerequisite missing "+needle)

    # Do not touch material.widthAnchor, cornerRadius, panel center, the
    # V139 native lens, tab font, window action controls or their animation.
    src=one(src,
'''        let listHeight = min(
            CGFloat(max(1, windowActions ? actionsCount : recent.count)) * 54 +
                (windowActions ? 0 : 12),
            maxListHeight)''',
'''        // SCARLET_V156_STABLE_PANEL_HEIGHT: both modes use at least the
        // three-action panel height from the first user screenshot.
        // A single recent app no longer shrinks the whole glass window.
        let listHeight = min(
            max(CGFloat(actionsCount * 54),
                CGFloat(max(1, recent.count)) * 54 + 24),
            maxListHeight)''',"base panel size")

    src=one(src,
'''            tabListHeightConstraint.constant =
                min(CGFloat(max(1, count)) * 54 + (windowActions ? 0 : 12),
                    maxListHeight)''',
'''            tabListHeightConstraint.constant = min(
                max(CGFloat(actionsCount * 54),
                    CGFloat(max(1, recent.count)) * 54 + 24),
                maxListHeight)''',"keep same height on tab switch")

    # Recent app row bloom is rendered by UIKit outside the button's own
    # 47pt frame, and requires horizontal optical clearance inside panel.
    # The PANEL remains unchanged; Window action buttons keep their bounds.
    src=one(src,
'''        rows.layoutMargins = UIEdgeInsets(top: 6, left: 12, bottom: 6, right: 12)''',
'''        // SCARLET_V156_ROW_OPTICAL_PAD: only inner recent controls use
        // optical breathing room. Preserve external panel width/height.
        rows.layoutMargins = UIEdgeInsets(top: 12, left: 18, bottom: 12, right: 18)''',
        "recent optical margins")

    # The earlier forced scroll clip:false can still be clipped at the
    # outer material border. Keep the glass panel itself a round mask but
    # ensure recent button's native bloom is inset from that mask.
    src=one(src,
'''        // SCARLET_V154_OUTSIDE_BACKDROP: one existing overlay with a direct touch fallback.''',
'''        // SCARLET_V154_OUTSIDE_BACKDROP: one existing overlay with a direct touch fallback.''',
        "backdrop marker presence") if False else src

    # Owner overlay's UIControl, remote scene UIGestureRecognizer and the
    # owner's window recognizer could all call collapse on one finger-down.
    # Make dismissal single-shot and log the COMPLETE closure path.
    src=one(src,
'''    var dismissOutside: (() -> Void)?
    // SCARLET_V155_OUTSIDE_HITTEST:''',
'''    var dismissOutside: (() -> Void)?
    private var queued = false
    // SCARLET_V156_OUTSIDE_TOUCH_TRACE: explicit event path for the native
    // backdrop, which is not a decorative overlay or a second UIWindow.
    // SCARLET_V155_OUTSIDE_HITTEST:''',"outside trace state")

    src=one(src,
'''            NSLog("[SCARLET_V154_OUTSIDE] stage=backdrop_touch outside=%d", outside ? 1 : 0)
            if outside {
                DispatchQueue.main.async { [weak self] in self?.dismissOutside?() }
            }''',
'''            NSLog("[SCARLET_V154_OUTSIDE] stage=backdrop_touch outside=%d", outside ? 1 : 0)
            NSLog("[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=backdrop_received outside=%d queued=%d", outside ? 1 : 0, queued ? 1 : 0)
            if outside && !queued {
                queued = true
                DispatchQueue.main.async { [weak self] in
                    guard let self else { return }
                    NSLog("[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=collapse_requested source=backdrop")
                    self.dismissOutside?()
                }
            }''',"dedup backdrop")

    src=one(src,
'''        let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)
        overlay.accessibilityIdentifier = "scarlet.v100.morph.backdrop"''',
'''        let overlay = SCOutsideDismissBackdrop(frame: owner.bounds)
        overlay.accessibilityIdentifier = "scarlet.v100.morph.backdrop"
        overlay.isUserInteractionEnabled = true
        NSLog("[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=backdrop_installed owner=%@",
              owner.windowScene?.session.persistentIdentifier ?? "unknown")''',"owner backdrop install")

    src=one(src,
'''    func gestureRecognizer(_ recognizer: UIGestureRecognizer,
                           shouldReceive touch: UITouch) -> Bool {
        outsidePanel(touch)
    }''',
'''    func gestureRecognizer(_ recognizer: UIGestureRecognizer,
                           shouldReceive touch: UITouch) -> Bool {
        let outside = outsidePanel(touch)
        NSLog("[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=window_should_receive outside=%d view=%@",
              outside ? 1 : 0, String(describing: recognizer.view))
        return outside
    }''',"window touch diagnostic")

    src=one(src,
'''        dismissQueued = true
        NSLog("[SCARLET_V150_OUTSIDE] phase=touch_down owner=%d",''',
'''        dismissQueued = true
        NSLog("[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=window_collapse_requested")
        NSLog("[SCARLET_V150_OUTSIDE] phase=touch_down owner=%d",''',
        "window dismissal diagnostic")

    src=one(src,
'''            guard backdrop.isUserInteractionEnabled else { return }
            backdrop.isUserInteractionEnabled = false''',
'''            guard backdrop.isUserInteractionEnabled else {
                NSLog("[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=collapse_duplicate")
                return
            }
            NSLog("[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=collapse_started")
            backdrop.isUserInteractionEnabled = false''',"actual collapse diagnostic")

    src=one(src,
'''                backdrop.removeFromSuperview()
                // Never strand the trigger permanently hidden''',
'''                backdrop.removeFromSuperview()
                NSLog("[SCARLET_V156_OUTSIDE_TOUCH_TRACE] stage=collapse_completed")
                // Never strand the trigger permanently hidden''',"actual close completion")

    # Remove duplicated overlay touchDown UIAction; direct backdrop event
    # is the only owner-level touch path. Window observer remains for any
    # other UIWindow overlapping this guest.
    start=src.index('''        overlay.addAction(UIAction { _ in
            NSLog("[SCARLET_V141_PICKER] dismiss=outside_tap")''')
    end=src.index('''        overlay.dismissOutside = { collapse({}) }''',start)
    src=src[:start]+'''        // V156: the subclass's touchesBegan is the ONE owner-overlay
        // dismissal path. The existing window observer handles other scenes.
'''+src[end:]
    # Ensure same effect for window actions and recent app rows.
    assert src.count(MARK)==1
    return src

def apply(root):
    f=root/FILE
    old=f.read_text()
    new=patch(old)
    if patch(new)!=new:raise ValueError("V156 not idempotent")
    if new!=old:f.write_text(new)
    print("[PASS] V156 panel height pinned across tabs, recent optical space, one outside owner and diagnostics")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v156_panel_size_outside.py <LiveContainer>")
    apply(Path(sys.argv[1]))
