#!/usr/bin/env python3
"""V136: stabilize full-screen guest geometry on rotation without scene recreation.

Address two observed code bugs: using a potentially unrelated key UIWindow as
viewport authority, and committing intermediate portrait-sized geometry after
windowScene orientation already became landscape. Retain the V129 portrait
touch-safe preference and the existing UIKit guest screen coordinate scheme.
"""
from pathlib import Path
import sys

DECO=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
DELEGATE=Path("LiveContainerSwiftUI/App/AppDelegate.swift")
MARK="SCARLET_V136_ROTATION_ATOMIC"

def once(s,old,new,label):
    n=s.count(old)
    if n!=1: raise ValueError(f"V136 {label}: expected one anchor, found {n}")
    return s.replace(old,new,1)

def decorated(s):
    if MARK in s:
        if s.count(MARK)!=1 or "nrgV136GeometryStable" not in s: raise ValueError("V136 partial ObjC")
        return s
    for t in ("NRG_V55_ROTATION_GEOMETRY","NRG_V64_PORTRAIT_TOUCH_FRAME","SCARLET_V129_VIEWPORT"):
        if t not in s:raise ValueError("V136 missing prerequisite "+t)
    # Host UIKit can report the new interface orientation before the current
    # UIWindow bounds have committed. Never publish mixed old/new dimensions.
    s=once(s,
        '''// NRG_V55_ROTATION_GEOMETRY: only one scene settings reconciliation per distinct rotation.
- (void)nrgV55ReconcileRotationGeometry {''',
        '''// SCARLET_V136_ROTATION_ATOMIC: never publish scene orientation with
// old UIKit window dimensions. Keep the old surface until UIKit commits the
// new host geometry; the UIWindowSceneDelegate schedules bounded retries.
- (BOOL)nrgV136GeometryStable:(UIWindow *)window {
    if (!window || !window.windowScene || CGRectIsEmpty(window.bounds)) return NO;
    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    if (orientation == UIInterfaceOrientationUnknown) return NO;
    CGSize size = window.bounds.size;
    const CGFloat tolerance = 1.0;
    BOOL portrait = UIInterfaceOrientationIsPortrait(orientation);
    BOOL landscape = UIInterfaceOrientationIsLandscape(orientation);
    if ((portrait && size.width > size.height + tolerance) ||
        (landscape && size.height > size.width + tolerance)) {
        NSLog(@"[SCARLET_V136_ROTATION] phase=defer orientation=%ld window=%.1fx%.1f",
              (long)orientation, size.width, size.height);
        return NO;
    }
    return YES;
}

// NRG_V55_ROTATION_GEOMETRY: only one scene settings reconciliation per distinct rotation.
- (void)nrgV55ReconcileRotationGeometry {''',
        "stable orientation preflight")
    s=once(s,
        '''    if (!window || !self.view.superview || CGRectIsEmpty(window.bounds)) return;
    CGSize size = window.bounds.size;
    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    // NRG_V61_LANDSCAPE_GUEST_RECOVERY:''',
        '''    if (!window || !self.view.superview || ![self nrgV136GeometryStable:window]) return;
    CGSize size = window.bounds.size;
    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    // NRG_V61_LANDSCAPE_GUEST_RECOVERY:''',
        "reconcile when stable")
    # V55's canonical build source already compares the guest to the
    # physical decorated viewport (viewportSize). Some older generated
    # snapshots still compare against the entire window (size). Accept ONLY
    # these two pinned shapes; update the legacy shape but do not clobber the
    # fixed version. Record a common 'viewport' variable for telemetry.
    legacy = '''    BOOL guestIsStale = fabs(guestSize.width - size.width) > 1.0 ||
                        fabs(guestSize.height - size.height) > 1.0;'''
    canonical = '''    CGSize viewportSize = self.view.bounds.size;
    BOOL guestIsStale = fabs(guestSize.width - viewportSize.width) > 1.0 ||
                        fabs(guestSize.height - viewportSize.height) > 1.0;'''
    if s.count(legacy) == 1 and canonical not in s:
        s = once(s, legacy,
                 '''    CGSize viewport = self.view.bounds.size;
    BOOL guestIsStale = fabs(guestSize.width - viewport.width) > 1.0 ||
                        fabs(guestSize.height - viewport.height) > 1.0;''',
                 "legacy stale check")
    elif s.count(canonical) == 1 and legacy not in s:
        s = once(s, canonical,
                 '''    CGSize viewport = self.view.bounds.size;
    BOOL guestIsStale = fabs(guestSize.width - viewport.width) > 1.0 ||
                        fabs(guestSize.height - viewport.height) > 1.0;''',
                 "canonical stale check")
    else:
        raise ValueError("V136 stale geometry: unrecognized or ambiguous pinned source")
    s=once(s,
        '''    [self.view setNeedsLayout];
    [self.appSceneVC.view setNeedsLayout];
    NSLog(@"[NRG_V55_GEOMETRY]''',
        '''    [self.view setNeedsLayout];
    [self.appSceneVC.view setNeedsLayout];
    NSLog(@"[SCARLET_V136_ROTATION] phase=commit orientation=%ld window=%.1fx%.1f viewport=%.1fx%.1f guest=%.1fx%.1f",
          (long)orientation, size.width, size.height,
          viewport.width, viewport.height, guestSize.width, guestSize.height);
    NSLog(@"[NRG_V55_GEOMETRY]''',
        "reconciliation diagnostics")
    s=once(s,
        '''    if (!window || !self.view.superview || CGRectIsEmpty(window.bounds)) return;
    // NRG_V58_EDGE_TO_EDGE_GUEST: UIKit window bounds are the only full-screen authority.''',
        '''    if (!window || !self.view.superview || ![self nrgV136GeometryStable:window]) return;
    // NRG_V58_EDGE_TO_EDGE_GUEST: UIKit window bounds are the only full-screen authority.''',
        "frame update when stable")
    return s

def dock(s):
    if MARK in s:
        if s.count(MARK)!=1 or "parent.window" not in s:raise ValueError("V136 partial Swift")
        return s
    if "NRG_V58_HOST_WINDOW_GEOMETRY" not in s:raise ValueError("V136 missing host geometry")
    old='''            let hostRect = parent.convert(hostScene.windows.first(where: {
                $0.isKeyWindow
            })?.bounds ?? hostScene.coordinateSpace.bounds,
                from: parent.window)
            if !hostRect.isEmpty && windowHostingView.frame != hostRect {
                windowHostingView.frame = hostRect
            }'''
    new='''            // SCARLET_V136_ROTATION_ATOMIC: read geometry ONLY from the
            // actual UIWindow containing this host. A keyboard, alert or
            // transient guest UIWindow can become key during orientation
            // transitions and has an unrelated coordinate space.
            if let hostWindow = parent.window {
                let bounds = hostWindow.bounds
                let orientation = hostScene.interfaceOrientation
                let mismatched = orientation.isPortrait
                    ? bounds.width > bounds.height + 1.0
                    : (orientation.isLandscape && bounds.height > bounds.width + 1.0)
                if !mismatched {
                    let hostRect = parent.convert(bounds, from: hostWindow)
                    if !hostRect.isEmpty && windowHostingView.frame != hostRect {
                        windowHostingView.frame = hostRect
                    }
                    NSLog("[SCARLET_V136_ROTATION] phase=host_commit width=%.1f height=%.1f", hostRect.width, hostRect.height)
                } else {
                    NSLog("[SCARLET_V136_ROTATION] phase=host_defer orientation=%ld width=%.1f height=%.1f",
                          orientation.rawValue, bounds.width, bounds.height)
                }
            }'''
    return once(s,old,new,"single authoritative host window")

def delegate(s):
    mark="SCARLET_V136_ROTATION_SETTLE"
    if mark in s:
        if s.count(mark)!=1:raise ValueError("V136 duplicate callbacks")
        return s
    if "func windowScene(_ windowScene: UIWindowScene, didUpdate" not in s:
        raise ValueError("V136 requires real UIWindowSceneDelegate callback")
    old='''    func windowScene(_ windowScene: UIWindowScene, didUpdate previousCoordinateSpace: UICoordinateSpace,
                     interfaceOrientation previousInterfaceOrientation: UIInterfaceOrientation,
                     traitCollection previousTraitCollection: UITraitCollection) {
        if #available(iOS 16.0, *) {
            DispatchQueue.main.async {
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }'''
    new='''    func windowScene(_ windowScene: UIWindowScene, didUpdate previousCoordinateSpace: UICoordinateSpace,
                     interfaceOrientation previousInterfaceOrientation: UIInterfaceOrientation,
                     traitCollection previousTraitCollection: UITraitCollection) {
        if #available(iOS 16.0, *) {
            // SCARLET_V136_ROTATION_SETTLE: didUpdate may arrive before
            // UIKit swaps the physical bounds. Recheck after the current
            // transaction and twice more; fixed count, no runaway timer.
            DispatchQueue.main.async {
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.10) { [weak windowScene] in
                guard let windowScene else { return }
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.28) { [weak windowScene] in
                guard let windowScene else { return }
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }'''
    return once(s,old,new,"bounded UIKit settled retries")

def apply(root:Path):
    changes=[]
    for rel,fn in ((DECO,decorated),(DOCK,dock),(DELEGATE,delegate)):
        p=root/rel
        if not p.is_file() or p.is_symlink():raise ValueError("V136 unavailable pinned file "+str(rel))
        old=p.read_text()
        new=fn(old)
        if fn(new)!=new:raise ValueError("V136 non-idempotent "+str(rel))
        changes.append((p,old,new))
    for p,old,new in changes:
        if new!=old:p.write_text(new)
    print("[PASS] V136 host UIWindow authority, no transitional guest-size updates, bounded settle retries")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v136_rotation_atomic.py <LiveContainer root>")
    apply(Path(sys.argv[1]))
