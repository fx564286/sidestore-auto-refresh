#!/usr/bin/env python3
"""V137: portrait touch settle, per-scene one-button authority, readable native glass."""
from pathlib import Path
import sys

DECO=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
BOOT=Path("LiveContainer/LCBootstrap.m")

def one(s, old, new, reason):
    n=s.count(old)
    if n!=1:raise ValueError("V137 "+reason+" expected one anchor; got "+str(n))
    return s.replace(old,new,1)

def decorated(s):
    if "SCARLET_V137_TOUCH_SETTLE" in s:return s
    for name in ("SCARLET_V136_ROTATION_ATOMIC","NRG_V73_APPLE_FLOATING_CONTROL"):
        if name not in s:raise ValueError("missing "+name)
    return one(s,'''    [super viewDidLayoutSubviews];
    [self nrgV73RestoreFloatingPosition];
    // SCARLET_V129_SINGLE_OWNER:''','''    [super viewDidLayoutSubviews];
    [self nrgV73RestoreFloatingPosition];
    // SCARLET_V137_TOUCH_SETTLE: the final UIKit layout wins over timed
    // scene callbacks. Reconcile ONLY on a new stable orientation or size;
    // never rebuild the guest or swallow touches with another overlay.
    UIWindow *host = self.view.window;
    if (self.isMaximized && self.appSceneVC.isAppRunning &&
        [self nrgV136GeometryStable:host]) {
        CGSize size = host.bounds.size;
        UIInterfaceOrientation orientation = host.windowScene.interfaceOrientation;
        if (!CGSizeEqualToSize(size, self.nrgV55LastHostSize) ||
            orientation != self.nrgV55LastHostOrientation) {
            NSLog(@"[SCARLET_V137_TOUCH] stage=layout_commit orientation=%ld width=%.1f height=%.1f",
                  (long)orientation,size.width,size.height);
            [self nrgV55ReconcileRotationGeometry];
        }
    }
    // SCARLET_V129_SINGLE_OWNER:''',"post-rotation touch frame")

def dock(s):
    if "SCARLET_V137_REGULAR_GLASS" in s:return s
    for name in ("SCARLET_V131_VISIBLE_GLASS_ACTIVATION","SCARLET_V132_GLASS_DRAG","SCARLET_V136_ROTATION_ATOMIC"):
        if name not in s:raise ValueError("missing "+name)
    s=one(s,"let glass = UIGlassEffect(style: .clear)",'''// SCARLET_V137_REGULAR_GLASS: standard UIKit glass reads
                // clearly over moving photos/video, unlike clear glass.
                let glass = UIGlassEffect(style: .regular)
                glass.tintColor = UIColor.systemBackground.withAlphaComponent(0.16)''',"standard native glass")
    s=one(s,"overlay.backgroundColor = UIColor.black.withAlphaComponent(0.08)",
          "overlay.backgroundColor = UIColor.black.withAlphaComponent(0.19)","contrast backdrop")
    s=one(s,"tabPicker.backgroundColor = UIColor.white.withAlphaComponent(0.04)",
          "tabPicker.backgroundColor = UIColor.white.withAlphaComponent(0.12)","tab housing")
    s=one(s,"tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.26)",
          "tabPicker.selectedSegmentTintColor = UIColor.white.withAlphaComponent(0.48)","visible selected tab")
    if s.count("item.backgroundColor = UIColor.white.withAlphaComponent(0.10)")!=3:
        raise ValueError("three row materials not found")
    s=s.replace("item.backgroundColor = UIColor.white.withAlphaComponent(0.10)",
                "item.backgroundColor = UIColor.secondarySystemBackground.withAlphaComponent(0.56)")
    if s.count("item.layer.borderColor = UIColor.white.withAlphaComponent(0.23).cgColor")!=3:
        raise ValueError("three row borders not found")
    s=s.replace("item.layer.borderColor = UIColor.white.withAlphaComponent(0.23).cgColor",
                "item.layer.borderColor = UIColor.separator.withAlphaComponent(0.42).cgColor")
    return s

def boot(s):
    if "SCARLET_V137_SCENE_OWNER" in s:return s
    if "SCARLET_V132_ONE_HANDLE" not in s:raise ValueError("V132 missing")
    s=one(s,'''- (BOOL)nativeAvailableInForeground {
    for (UIScene *candidate in UIApplication.sharedApplication.connectedScenes) {
        if (![candidate isKindOfClass:UIWindowScene.class] ||
            candidate.activationState != UISceneActivationStateForegroundActive) continue;
        UIWindowScene *active = (UIWindowScene *)candidate;
        for (UIWindow *window in active.windows) {
            if ([self containsVirtualHandle:window]) return YES;
        }
    }
    return NO;
}''','''// SCARLET_V137_SCENE_OWNER: only THIS foreground scene can retire its
// fallback. A native handle from another guest must never hide this one.
- (BOOL)nativeAvailableInScene:(UIWindowScene *)scene {
    if (!scene || scene.activationState != UISceneActivationStateForegroundActive) return NO;
    for (UIWindow *window in scene.windows) {
        if (window.hidden || window.alpha < 0.05) continue;
        if ([self containsVirtualHandle:window]) return YES;
    }
    return NO;
}''',"scope button owner")
    start=s.index("- (void)retireAllFallbacks:(NSString *)reason {")
    end=s.index("\n- (void)virtualReady:(NSNotification *)notice {",start)
    s=s[:start]+s[end+1:]
    s=one(s,'''    // SCARLET_V132_ONE_HANDLE: never trust a speculative notification.
    // Cross-scene native handles also own the sole visible edge affordance.
    if ([self nativeAvailableInForeground])
        [self retireAllFallbacks:@"native_V73_ready"];''','''    UIWindowScene *scene = [notice.object isKindOfClass:UIWindowScene.class] ? notice.object : nil;
    if ([self nativeAvailableInScene:scene])
        [self retireFallbackInScene:scene reason:@"native_V73_ready"];''',"ready notification")
    s=one(s,'''    if ([self nativeAvailableInForeground]) {
        [self retireAllFallbacks:@"native_exists_before_fallback"];
        return;
    }''','''    if ([self nativeAvailableInScene:scene]) {
        [self retireFallbackInScene:scene reason:@"native_exists_before_fallback"];
        return;
    }''',"initial owner")
    s=one(s,'''        if ([weakPresenter nativeAvailableInForeground]) {
            [weakPresenter retireAllFallbacks:@"deferred_native_attached"];
        }''','''        if ([weakPresenter nativeAvailableInScene:scene]) {
            [weakPresenter retireFallbackInScene:scene reason:@"deferred_native_attached"];
        }''',"delayed owner")
    s=one(s,"return view.userInteractionEnabled && view.window != nil;",
       '''return view.userInteractionEnabled && view.window != nil &&
            CGRectIntersectsRect([view convertRect:view.bounds toView:view.window],
                                 view.window.bounds);''',"offscreen native button")
    if "nativeAvailableInForeground" in s or "retireAllFallbacks:" in s:
        raise ValueError("V137 stale cross-scene owner")
    return s

def apply(root):
    changed=[]
    for rel,fn in ((DECO,decorated),(DOCK,dock),(BOOT,boot)):
        path=root/rel
        if not path.is_file() or path.is_symlink():raise ValueError("V137 unavailable "+str(rel))
        before=path.read_text()
        after=fn(before)
        if fn(after)!=after:raise ValueError("non-idempotent "+str(rel))
        changed.append((path,before,after))
    for p,a,b in changed:
        if a!=b:p.write_text(b)
    print("[PASS] V137 touch-safe scene, readable glass, one handle per guest scene")
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("pass LiveContainer root")
    apply(Path(sys.argv[1]))
