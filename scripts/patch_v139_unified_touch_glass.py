#!/usr/bin/env python3
"""V139: one host guest-picker destination, continuous 2D finger glass.

A Classic/Direct guest can run in a different process than the host's SwiftUI
module, so do not claim an ObjC class lookup proves the host picker is loaded.
Keep both established floating BUTTON OWNERS in their exclusive contexts, but
route both to the single native MultitaskDockManager picker implementation.
No additional buttons, windows, menus, sign-in, pairing, or JIT mutations.
"""
from pathlib import Path
import sys

BOOT = Path('LiveContainer/LCBootstrap.m')
DOCK = Path('MultitaskSupport/MultitaskDockView.swift')
DECORATED = Path('MultitaskSupport/DecoratedAppSceneViewController.m')
SHELL = Path('LiveContainerSwiftUI/Views/V3UnifiedShell.swift')
MARK = 'SCARLET_V139_UNIFIED_GUEST_ACTION'


def one(s, before, after, reason):
    n=s.count(before)
    if n != 1:
        raise ValueError(f'V139 {reason}: expected 1 source anchor, found {n}')
    return s.replace(before,after,1)


def boot(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'nrg-guest-controls' not in s or 'scarlet.v139.direct.glass.touch' not in s:
            raise ValueError('V139 partial Direct entry')
        return s
    for expected in ('SCARLET_V138_FUNCTIONAL_OWNER','SCARLET_V105_DIRECT_UNIFIED_MORPH',
                     'SCGuestMorphPresenter','SCARLET_V137_SCENE_OWNER'):
        if expected not in s: raise ValueError('V139 incompatible Direct owner: '+expected)
    # The previous 'scheme://' URL has no recognized host action; it never
    # guarantees any picker, even when openURL completion reports success.
    s=one(s, 'NSURL *returnURL = [NSURL URLWithString:@"scarletcrystal251://"];',
        '''// SCARLET_V139_UNIFIED_GUEST_ACTION: the exact same host-owned
    // picker as V73, reached via a documented app route when Classic mode
    // cannot load the host's Swift module in this process.
    NSURL *returnURL = [NSURL URLWithString:@"scarletcrystal251://nrg-guest-controls"];''',
        'replace inert Direct URL with canonical host picker route')
    s=one(s, 'NSLog(@"[SCARLET_V138_ACTION] fallback=host_link accepted=%d", accepted);',
        'NSLog(@"[SCARLET_V139_ACTION] route=host_picker_request accepted=%d", accepted);',
        'record actual URL submission result without claiming UI appeared')
    # Track touch-down, touch-move and pan for the sole existing UIButton.
    s=one(s,
        '    [handle addTarget:self action:@selector(openShared:) forControlEvents:UIControlEventTouchUpInside];',
        '''    [handle addTarget:self action:@selector(openShared:) forControlEvents:UIControlEventTouchUpInside];
    [handle addTarget:self action:@selector(reactToGlassTouch:forEvent:)
       forControlEvents:(UIControlEventTouchDown | UIControlEventTouchDragInside |
                         UIControlEventTouchDragOutside | UIControlEventTouchUpInside |
                         UIControlEventTouchUpOutside | UIControlEventTouchCancel)];''',
        'instrument same Direct UIControl, do not make another button')
    s=one(s,
        '''    [handle insertSubview:material atIndex:0];''',
        '''    [handle insertSubview:material atIndex:0];
    // Native glass stays installed. Only a lightweight highlight follows
    // actual 2D touches; do not swap effect mid-gesture or reblur video.
    CAGradientLayer *finger = [CAGradientLayer layer];
    finger.name = @"scarlet.v139.direct.glass.touch";
    finger.type = kCAGradientLayerRadial;
    finger.frame = handle.bounds;
    finger.colors = @[(id)[UIColor.whiteColor colorWithAlphaComponent:0.38].CGColor,
                      (id)[UIColor.whiteColor colorWithAlphaComponent:0.08].CGColor,
                      (id)[UIColor.whiteColor colorWithAlphaComponent:0.00].CGColor];
    finger.locations = @[@0.0, @0.38, @1.0];
    finger.startPoint = CGPointMake(0.5, 0.5);
    finger.endPoint = CGPointMake(1.1, 1.1);
    [material.contentView.layer addSublayer:finger];''',
        'persistent touch-dependent optical highlight on same control')
    s=one(s,
        '''- (void)dragHandle:(UIPanGestureRecognizer *)gesture {
    UIView *button = gesture.view;''',
        '''- (void)updateDirectGlass:(UIView *)button atPoint:(CGPoint)point {
    if (!button || button.bounds.size.width < 1 || button.bounds.size.height < 1) return;
    CGFloat x = MAX(0, MIN(1, point.x / button.bounds.size.width));
    CGFloat y = MAX(0, MIN(1, point.y / button.bounds.size.height));
    [CATransaction begin];
    [CATransaction setDisableActions:YES];
    for (UIView *subview in button.subviews) {
        if (![subview isKindOfClass:UIVisualEffectView.class]) continue;
        CALayer *container = ((UIVisualEffectView *)subview).contentView.layer;
        for (CALayer *layer in container.sublayers) {
            if (![layer isKindOfClass:CAGradientLayer.class] ||
                ![layer.name isEqualToString:@"scarlet.v139.direct.glass.touch"]) continue;
            CAGradientLayer *glint = (CAGradientLayer *)layer;
            glint.frame = button.bounds;
            glint.startPoint = CGPointMake(x, y);
            glint.endPoint = CGPointMake(x + 0.58, y + 0.58);
        }
    }
    [CATransaction commit];
}
- (void)reactToGlassTouch:(UIButton *)button forEvent:(UIEvent *)event {
    UITouch *touch = [[event touchesForView:button] anyObject];
    if (!touch) return;
    [self updateDirectGlass:button atPoint:[touch locationInView:button]];
    NSLog(@"[SCARLET_V139_GLASS] surface=direct finger=tracked phase=%ld", (long)touch.phase);
}
- (void)dragHandle:(UIPanGestureRecognizer *)gesture {
    UIView *button = gesture.view;
    [self updateDirectGlass:button atPoint:[gesture locationInView:button]];''',
        'shared Direct touch coordinate for click and drag')
    return s

def decorated(s):
    # The functioning V73 host button uses the same glass-touch semantics as
    # Direct. Never introduce a second button or observer to shadow it.
    if MARK in s:
        if s.count(MARK)!=1 or 'scarlet.v139.hosted.glass.touch' not in s:
            raise ValueError('V139 partial host button')
        return s
    for expected in ('NRG_V73_APPLE_FLOATING_CONTROL', 'nrgV100TapMorph:',
                     'SCARLET_V103_VIRTUAL_ONLY_CONTROL','SCARLET_V136_ROTATION_ATOMIC'):
        if expected not in s:raise ValueError('V139 canonical host control missing '+expected)
    s=one(s,
        '    [overflow insertSubview:nrgV73Material atIndex:0];',
        '''    [overflow insertSubview:nrgV73Material atIndex:0];
    // SCARLET_V139_UNIFIED_GUEST_ACTION: retain the working V73 button.
    // Only its specular light moves; no duplicate overlay or gesture owner.
    CAGradientLayer *finger = [CAGradientLayer layer];
    finger.name = @"scarlet.v139.hosted.glass.touch";
    finger.type = kCAGradientLayerRadial;
    finger.frame = CGRectMake(0, 0, 44, 44);
    finger.colors = @[(id)[UIColor.whiteColor colorWithAlphaComponent:0.38].CGColor,
                      (id)[UIColor.whiteColor colorWithAlphaComponent:0.08].CGColor,
                      (id)[UIColor.whiteColor colorWithAlphaComponent:0].CGColor];
    finger.locations = @[@0.0, @0.38, @1.0];
    finger.startPoint = CGPointMake(0.5, 0.5);
    finger.endPoint = CGPointMake(1.1, 1.1);
    [nrgV73Material.contentView.layer addSublayer:finger];
    [overflow addTarget:self action:@selector(nrgV139HostedGlassTouch:forEvent:)
      forControlEvents:(UIControlEventTouchDown | UIControlEventTouchDragInside |
                        UIControlEventTouchDragOutside | UIControlEventTouchUpInside |
                        UIControlEventTouchUpOutside | UIControlEventTouchCancel)];''',
        'native hosted V73 touch tracking')
    s=one(s,
        '- (void)nrgV73DragFloatingOverflow:(UIPanGestureRecognizer *)pan {',
        '''- (void)nrgV139UpdateHostedGlassAt:(CGPoint)point inButton:(UIView *)button {
    if (!button || button.bounds.size.width <= 0 || button.bounds.size.height <= 0) return;
    CGFloat x = MAX(0, MIN(1, point.x / button.bounds.size.width));
    CGFloat y = MAX(0, MIN(1, point.y / button.bounds.size.height));
    [CATransaction begin];
    [CATransaction setDisableActions:YES];
    for (UIView *child in button.subviews) {
        if (![child isKindOfClass:UIVisualEffectView.class]) continue;
        for (CALayer *layer in ((UIVisualEffectView *)child).contentView.layer.sublayers) {
            if (![layer isKindOfClass:CAGradientLayer.class] ||
                ![layer.name isEqualToString:@"scarlet.v139.hosted.glass.touch"]) continue;
            CAGradientLayer *glint = (CAGradientLayer *)layer;
            glint.startPoint = CGPointMake(x, y);
            glint.endPoint = CGPointMake(x + 0.58, y + 0.58);
        }
    }
    [CATransaction commit];
}
- (void)nrgV139HostedGlassTouch:(UIButton *)button forEvent:(UIEvent *)event {
    UITouch *touch = [[event touchesForView:button] anyObject];
    if (!touch) return;
    [self nrgV139UpdateHostedGlassAt:[touch locationInView:button] inButton:button];
    NSLog(@"[SCARLET_V139_GLASS] surface=hosted finger=tracked phase=%ld", (long)touch.phase);
}
- (void)nrgV73DragFloatingOverflow:(UIPanGestureRecognizer *)pan {
    [self nrgV139UpdateHostedGlassAt:[pan locationInView:self.nrgWindowOverflow]
                                      inButton:self.nrgWindowOverflow];''',
        'drag point controls native V73 light')
    return s

PANEL_TRACKER = '''// SCARLET_V139_PANEL_TOUCH: optical tracking is decoupled from every button,
// segmented control, and scroll view. Gestures always remain actionable.
@available(iOS 26.0, *)
private final class SCPanelGlassFingerTracker: NSObject, UIGestureRecognizerDelegate {
    weak var rim: SCNativeGlassRimView?
    weak var surface: UIView?

    init(rim: SCNativeGlassRimView, surface: UIView) {
        self.rim = rim
        self.surface = surface
        super.init()
    }

    @objc func track(_ touch: UILongPressGestureRecognizer) {
        guard let surface, let rim, surface.bounds.width > 1,
              surface.bounds.height > 1 else { return }
        switch touch.state {
        case .began, .changed:
            let pos = touch.location(in: surface)
            let x = min(1, max(0, pos.x / surface.bounds.width))
            let y = min(1, max(0, pos.y / surface.bounds.height))
            rim.followPoint(x: x, y: y)
            NSLog("[SCARLET_V139_GLASS] surface=panel finger=tracked")
        case .ended, .cancelled, .failed:
            rim.releasePoint()
        default: break
        }
    }

    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
      shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool {
        true // never break rows, tabs, or scrolling
    }
}

'''


def dock(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'SCARLET_V139_PANEL_TOUCH' not in s:
            raise ValueError('V139 partial glass UI')
        return s
    for expected in ('SCARLET_V131_REFERENCE_LIQUID_GLASS',
                     'SCARLET_V131_VISIBLE_GLASS_ACTIVATION',
                     'SCARLET_V132_GLASS_DRAG',
                     'SCARLET_V137_REGULAR_GLASS',
                     '@objc(SCUnifiedGuestUIBridge)'):
        if expected not in s: raise ValueError('V139 missing canonical Swift renderer: '+expected)
    # Make UIGlassEffect the first and only effect in the panel lifecycle.
    # V131 incorrectly set nil on creation and changed to glass 0.35s later.
    s=one(s,
        '''            // UIKit can skip native glass while its parent is alpha-zero.
            // Defer installation until the surface is fully visible.
            material.effect = nil
            NSLog("[SCARLET_V131_GLASS] status=deferred_until_visible native=1")''',
        '''            // SCARLET_V139_UNIFIED_GUEST_ACTION: sample live native
            // refraction from first layout through close; no mid-flight swap.
            // Preserve the original transparent lens throughout its life:
            // V137's later .regular swap produced the opaque grey/white flash.
            let steadyGlass = UIGlassEffect(style: .clear)
            steadyGlass.isInteractive = true
            material.effect = steadyGlass
            NSLog("[SCARLET_V139_GLASS] surface=panel material=persistent_native")''',
        'eliminate transition from nil to white/opaque glass')
    # V137 earlier changed the completion's .clear glass to .regular.
    obsolete='''        }, completion: { _ in
            // SCARLET_V131_VISIBLE_GLASS_ACTIVATION: install only when visible.
            guard overlay.superview != nil else { return }
            if #available(iOS 26.0, *), !UIAccessibility.isReduceTransparencyEnabled {
                // SCARLET_V137_REGULAR_GLASS: standard native refraction,
                // dynamic system tint, not unbounded background transparency.
                let glass = UIGlassEffect(style: .regular)
                glass.tintColor = UIColor.systemBackground.withAlphaComponent(0.16)
                glass.isInteractive = true
                UIView.animate(withDuration: reduceMotion ? 0 : 0.20) {
                    material.effect = glass
                }
                NSLog("[SCARLET_V131_GLASS] status=materialized_after_visible interactive=1")
            }
        })'''
    # Be strict; drifted code fails rather than layering another animation.
    if obsolete not in s:
        raise ValueError('V139 delayed material switch changed; inspect actual source')
    s=one(s,obsolete,'''        })
        // SCARLET_V131_VISIBLE_GLASS_ACTIVATION retired by V139: the
        // native material was installed before presentation, stays stable.''',
        'remove second native material mutation after fade')
    s=one(s,
        '''@available(iOS 26.0, *)
private final class SCNativeGlassRimView: UIView {''',
        PANEL_TRACKER+'''@available(iOS 26.0, *)
private final class SCNativeGlassRimView: UIView {''',
        'one panel tracker class, no new rendering root')
    s=one(s,
        '''    private let highlight = CAGradientLayer()
''',
        '''    private let highlight = CAGradientLayer()
    private let contact = CAGradientLayer()
''',
        'radial touch illumination')
    s=one(s,
        '''        layer.addSublayer(highlight)
''',
        '''        layer.addSublayer(highlight)
        contact.type = .radial
        contact.colors = [UIColor.white.withAlphaComponent(0.30).cgColor,
                          UIColor.white.withAlphaComponent(0.08).cgColor,
                          UIColor.white.withAlphaComponent(0.0).cgColor]
        contact.locations = [0, 0.36, 1]
        contact.startPoint = CGPoint(x: 0.5, y: 0.5)
        contact.endPoint = CGPoint(x: 1.1, y: 1.1)
        contact.opacity = 0
        layer.addSublayer(contact)
''',
        'one soft specular spot')
    s=one(s,
        '''        highlight.frame = bounds
        CATransaction.commit()''',
        '''        highlight.frame = bounds
        contact.frame = bounds
        CATransaction.commit()''',
        'continuous gradient geometry')
    s=one(s,
        '''    func followFinger(_ fraction: CGFloat) {''',
        '''    func followPoint(x: CGFloat, y: CGFloat) {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        contact.opacity = 1
        contact.startPoint = CGPoint(x: x, y: y)
        contact.endPoint = CGPoint(x: x + 0.55, y: y + 0.55)
        highlight.startPoint = CGPoint(x: max(0.05, x - 0.18), y: max(0, y - 0.15))
        highlight.endPoint = CGPoint(x: min(1, x + 0.22), y: min(1, y + 0.23))
        CATransaction.commit()
    }

    func releasePoint() {
        CATransaction.begin()
        CATransaction.setDisableActions(true)
        contact.opacity = 0
        CATransaction.commit()
    }

    func followFinger(_ fraction: CGFloat) {''',
        '2D touch motion rather than only tab x fraction')
    s=one(s,
        '''                opticalRim.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor)
            ])''',
        '''                opticalRim.bottomAnchor.constraint(equalTo: material.contentView.bottomAnchor)
            ])
            let fingerTracker = SCPanelGlassFingerTracker(rim: opticalRim, surface: material.contentView)
            let fingerGesture = UILongPressGestureRecognizer(
                target: fingerTracker, action: #selector(SCPanelGlassFingerTracker.track(_:)))
            fingerGesture.minimumPressDuration = 0
            fingerGesture.allowableMovement = 10000
            fingerGesture.cancelsTouchesInView = false
            fingerGesture.delaysTouchesBegan = false
            fingerGesture.delegate = fingerTracker
            objc_setAssociatedObject(material, UnsafeRawPointer(bitPattern: 0x139)!,
                fingerTracker, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
            material.contentView.addGestureRecognizer(fingerGesture)
            NSLog("[SCARLET_V139_GLASS] surface=panel finger_tracking=installed")''',
        'panel-wide coordinate tracking that preserves UIControls')
    return s


def shell(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'nrg-guest-controls' not in s:
            raise ValueError('V139 host deep link partial')
        return s
    if 'NRG_V60_ISLAND_ROUTE' not in s or 'private func dispatchURL(_ url: URL)' not in s:
        raise ValueError('V139 missing V3 host URL dispatcher')
    # This uses the existing *host* UI root and the ONE V72 picker. It never
    # creates a second native floating button, bridge or custom panel.
    needle='''    private func dispatchURL(_ url: URL) {
'''
    new='''    private func dispatchURL(_ url: URL) {
        // SCARLET_V139_UNIFIED_GUEST_ACTION: Classic/Direct cannot assume
        // the host's SwiftUI binary exists in its injected guest process.
        // Deliver exactly one explicit request to the existing host picker.
        if url.scheme?.lowercased() == "scarletcrystal251",
           url.host?.lowercased() == "nrg-guest-controls" {
            sharedModel.selectedTab = .apps
            DispatchQueue.main.async {
                let scene = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
                    .first { $0.activationState == .foregroundActive }
                guard let root = scene?.windows.first(where: {
                    !$0.isHidden && $0.windowLevel == .normal && $0.rootViewController != nil
                })?.rootViewController, root.view.window != nil else {
                    NSLog("[SCARLET_V139_ACTION] route=host_picker result=deferred_unavailable")
                    return
                }
                MultitaskDockManager.shared.nrgV72PresentGuestSwitcher(
                    from: root, sourceView: root.view)
                NSLog("[SCARLET_V139_ACTION] route=host_picker result=dispatched")
            }
            return
        }
'''
    return one(s,needle,new,'host-only canonical picker deep link')


def apply(root):
    plans = ((BOOT,boot),(DECORATED,decorated),(DOCK,dock),(SHELL,shell))
    changed=[]
    for rel,fn in plans:
        file=root/rel
        if not file.is_file() or file.is_symlink(): raise ValueError('missing pinned source '+str(file))
        old=file.read_text(encoding='utf-8')
        new=fn(old)
        if fn(new)!=new: raise ValueError('V139 non-idempotent '+str(rel))
        changed.append((file,old,new))
    for file,old,new in changed:
        if old!=new:file.write_text(new,encoding='utf-8')
    print('[PASS] V139 stable native glass + 2D finger tracking + one host picker route')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v139_unified_touch_glass.py <LiveContainer>')
    apply(Path(sys.argv[1]))
