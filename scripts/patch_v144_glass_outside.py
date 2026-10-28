#!/usr/bin/env python3
"""V144: single native guest picker: touch-reactive glass and window-level outside dismissal.

A UIWindow-level gesture is necessary because an iOS 27 guest window can be
reparented above the original UIControl backdrop after scene reconciliation.
The gesture exists only while the ONE native panel is shown; the panel, buttons
and guest action handlers remain the existing single owners.
"""
from pathlib import Path
import sys

DOCK=Path('MultitaskSupport/MultitaskDockView.swift')
MARK='SCARLET_V144_WINDOW_OUTSIDE_TAP'

def one(s,a,b,label):
    n=s.count(a)
    if n!=1:raise ValueError(f'V144 {label}: expected 1 source match, got {n}')
    return s.replace(a,b,1)

OBSERVER="""// SCARLET_V144_WINDOW_OUTSIDE_TAP: the UIWindow receives touches even when a
// previously active guest scene has been moved above the picker backdrop.
// One temporary recognizer; never another button, view, or UIWindow.
private final class SCOutsideGlassTapObserver: NSObject, UIGestureRecognizerDelegate {
    weak var owner: UIWindow?
    weak var panel: UIView?
    var dismiss: (() -> Void)?

    init(owner: UIWindow, panel: UIView, dismiss: @escaping () -> Void) {
        self.owner = owner
        self.panel = panel
        self.dismiss = dismiss
        super.init()
    }

    func gestureRecognizer(_ recognizer: UIGestureRecognizer,
                           shouldReceive touch: UITouch) -> Bool {
        guard let owner, let panel, panel.window === owner else { return false }
        return !panel.convert(panel.bounds, to: owner).contains(touch.location(in: owner))
    }

    @objc func outsideTap(_ recognizer: UITapGestureRecognizer) {
        guard recognizer.state == .ended,
              let owner, let panel, panel.window === owner else { return }
        if panel.convert(panel.bounds, to: owner).contains(recognizer.location(in: owner)) {
            return
        }
        NSLog("[SCARLET_V144_PICKER] dismissed=window_outside_tap")
        dismiss?()
    }
}

"""

def patch(s):
    if MARK in s:
        for required in ('class SCOutsideGlassTapObserver','SCARLET_V144_LENS_DRAG',
                         'SCARLET_V144_GLASS_INSTALLED'):
            if required not in s:raise ValueError('V144 incomplete UI source: '+required)
        if s.count(MARK)!=1:raise ValueError('duplicate V144 picker')
        return s
    for pre in ('SCARLET_V141_OUTSIDE_TAP_DISMISS','SCARLET_V139_PANEL_TOUCH',
                'SCARLET_V140_FINGER_DEFORMATION', 'SCARLET_V131_REFERENCE_LIQUID_GLASS'):
        if pre not in s:raise ValueError('V144 missing prerequisite '+pre)
    s=one(s,
          '// SCARLET_V139_PANEL_TOUCH: optical tracking is decoupled',
          OBSERVER+'// SCARLET_V139_PANEL_TOUCH: optical tracking is decoupled',
          'window-level outside observer')
    s=one(s,'''    weak var rim: SCNativeGlassRimView?
    weak var surface: UIView?

    init(rim: SCNativeGlassRimView, surface: UIView) {
        self.rim = rim
        self.surface = surface''',
          '''    weak var rim: SCNativeGlassRimView?
    weak var surface: UIView?
    weak var lens: UIVisualEffectView?

    init(rim: SCNativeGlassRimView, surface: UIView,
         lens: UIVisualEffectView) {
        self.rim = rim
        self.surface = surface
        self.lens = lens''',
          'retain panel geometry without duplicate glass surface')
    s=one(s,
          '''            rim.followPoint(x: x, y: y)
            NSLog("[SCARLET_V139_GLASS] surface=panel finger=tracked")''',
          '''            rim.followPoint(x: x, y: y)
            // SCARLET_V144_LENS_DRAG: visibly deform the native lens as
            // the finger moves. This is optical geometry, not opacity swap.
            if !UIAccessibility.isReduceMotionEnabled {
                let shiftX = (x - 0.5) * 12.0
                let shiftY = (y - 0.5) * 12.0
                let stretchX = 1.0 + abs(x - 0.5) * 0.038
                let stretchY = 1.0 + abs(y - 0.5) * 0.038
                lens?.transform = CGAffineTransform(
                    translationX: shiftX, y: shiftY)
                    .scaledBy(x: stretchX, y: stretchY)
            }
            NSLog("[SCARLET_V144_GLASS] phase=finger_moved x=%.2f y=%.2f", x, y)''',
          'visibly follow touch position')
    s=one(s,
          '''        case .ended, .cancelled, .failed:
            rim.releasePoint()
        default: break''',
          '''        case .ended, .cancelled, .failed:
            rim.releasePoint()
            if let lens {
                UIView.animate(withDuration: UIAccessibility.isReduceMotionEnabled ? 0 : 0.23,
                               delay: 0, usingSpringWithDamping: 0.82,
                               initialSpringVelocity: 0,
                               options: [.beginFromCurrentState],
                               animations: { lens.transform = .identity },
                               completion: nil)
            }
        default: break''',
          'restore lens without swapping the native glass')
    s=one(s,
          '''let fingerTracker = SCPanelGlassFingerTracker(rim: opticalRim, surface: material.contentView)''',
          '''let fingerTracker = SCPanelGlassFingerTracker(rim: opticalRim,
                surface: material.contentView, lens: material)''',
          'reuse the one existing finger tracker')
    s=one(s,
          '''        contact.colors = [UIColor.white.withAlphaComponent(0.30).cgColor,
                          UIColor.white.withAlphaComponent(0.08).cgColor,''',
          '''        contact.colors = [UIColor.white.withAlphaComponent(0.66).cgColor,
                          UIColor.white.withAlphaComponent(0.19).cgColor,''',
          'stronger localized Fresnel contact highlight')
    s=one(s,
          '''        material.layer.cornerCurve = .continuous''',
          '''        material.layer.cornerCurve = .continuous
        // V144: native clear glass remains the only refraction material.
        // Bright edge optics are visible against both light and dark video.
        material.layer.borderWidth = 1.0
        material.layer.borderColor = UIColor.white.withAlphaComponent(0.62).cgColor
        NSLog("[SCARLET_V144_GLASS_INSTALLED] lens=native_clear border=continuous")''',
          'native glass boundary cue')
    s=one(s,
          '''        let sourceOrigin = sourceView.convert(sourceView.bounds, to: owner)''',
          '''        let sourceOrigin = sourceView.convert(sourceView.bounds, to: owner)
        // Installed only while this single picker is presented.
        let outsideTap = UITapGestureRecognizer()
        outsideTap.cancelsTouchesInView = true''',
          'scoped UIWindow touch filter')
    s=one(s,
          '''let collapse: (@escaping () -> Void) -> Void = { [weak overlay, weak material, weak sourceView] completion in
            guard let backdrop = overlay''',
          '''let collapse: (@escaping () -> Void) -> Void = {
            [weak overlay, weak material, weak sourceView, weak outsideTap, weak owner] completion in
            if let outsideTap { owner?.removeGestureRecognizer(outsideTap) }
            guard let backdrop = overlay''',
          'remove window gesture when picker collapses')
    # The V141 action is the stable anchor. Later host-level layout
    # bookkeeping can sit between it and the recent-apps presentation.
    # Never require adjacency to 'if recent.isEmpty'.
    s=one(s,
          '''            NSLog("[SCARLET_V141_PICKER] dismiss=outside_tap")
            collapse({})
        }, for: .touchDown)''',
          '''            NSLog("[SCARLET_V141_PICKER] dismiss=outside_tap")
            collapse({})
        }, for: .touchDown)
        let outsideObserver = SCOutsideGlassTapObserver(
            owner: owner, panel: material, dismiss: { collapse({}) })
        outsideTap.addTarget(outsideObserver,
            action: #selector(SCOutsideGlassTapObserver.outsideTap(_:)))
        outsideTap.delegate = outsideObserver
        objc_setAssociatedObject(overlay, UnsafeRawPointer(bitPattern: 0x144)!,
            outsideObserver, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
        owner.addGestureRecognizer(outsideTap)
        NSLog("[SCARLET_V144_PICKER] outside_guard=window_attached")''',
          'attach outside tap after existing V141 backdrop action')

    return s

def apply(root):
    file=root/DOCK
    if not file.is_file() or file.is_symlink():raise ValueError('missing pinned picker source')
    old=file.read_text(encoding='utf-8')
    new=patch(old)
    if patch(new)!=new:raise ValueError('V144 picker patch not idempotent')
    if new!=old:file.write_text(new,encoding='utf-8')
    from patch_v144_button_glass import apply as apply_buttons
    apply_buttons(root)
    print('[PASS] V144 window-scoped outside dismiss and native interactive glass lens')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v144_glass_outside.py <LiveContainer>')
    apply(Path(sys.argv[1]))
