#!/usr/bin/env python3
"""V55: orientation-safe fullscreen host geometry for retained LiveContainer guests.

Applies only after V38 and V47 on the workflow's pinned LiveContainer revision.
Does not resize windowed guests, recreate guest scenes, or change JIT/signing.
"""
from pathlib import Path
import sys

MARK="NRG_V55_ROTATION_GEOMETRY"

def one(s,old,new,label):
    n=s.count(old)
    if n!=1:
        raise RuntimeError(f"V55 {label}: expected 1 anchor, got {n}")
    return s.replace(old,new,1)

def header(s):
    if MARK in s: return s
    return one(s,"- (void)updateVerticalConstraints;\n",
       "- (void)updateVerticalConstraints;\n"
       "// "+MARK+": host rotation recovery for visible maximized guests.\n"
       "- (void)nrgV55ReconcileRotationGeometry;\n","header")

def decorated(s):
    if MARK in s: return s
    if "NRG_V38_MAXIMIZED_SAFE_AREA_FRAME" not in s:
        raise RuntimeError("apply V38 before V55")
    s=one(s,"@property(nonatomic) bool isAppTerminationRequested;",
      "@property(nonatomic) bool isAppTerminationRequested;\n"
      "// "+MARK+": avoid repeated scene updates for the same host size.\n"
      "@property(nonatomic) CGSize nrgV55LastHostSize;\n"
      "@property(nonatomic) UIInterfaceOrientation nrgV55LastHostOrientation;",
      "rotation state")
    s=one(s,"UIInterfaceOrientation currentOrientation = UIApp.statusBarOrientation;",
      "UIInterfaceOrientation currentOrientation = self.view.window.windowScene.interfaceOrientation;\n"
      "        if (currentOrientation == UIInterfaceOrientationUnknown) currentOrientation = UIApp.statusBarOrientation;",
      "scene orientation")
    old="""- (void)updateMaximizedFrameWithSettings:(UIMutableApplicationSceneSettings *)settings {
    CGRect maxFrame = UIEdgeInsetsInsetRect(self.view.window.frame, [self updateMaximizedSafeAreaWithSettings:settings]);
    self.view.frame = maxFrame;
}"""
    new="""// """+MARK+""": only one scene settings reconciliation per distinct rotation.
- (void)nrgV55ReconcileRotationGeometry {
    NSAssert([NSThread isMainThread], @"rotation geometry must run on main");
    if (!self.isMaximized || !self.appSceneVC.isAppRunning || self.view.hidden) return;
    UIWindow *window = self.view.window;
    if (!window || !self.view.superview || CGRectIsEmpty(window.bounds)) return;
    CGSize size = window.bounds.size;
    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    // NRG_V61_LANDSCAPE_GUEST_RECOVERY: during UIKit rotation, the host
    // size can be correct while the retained guest is still portrait-sized.
    // Do not let a cached rotation token suppress a needed scene resize.
    CGSize guestSize = self.appSceneVC.view.bounds.size;
    BOOL guestIsStale = fabs(guestSize.width - size.width) > 1.0 ||
                        fabs(guestSize.height - size.height) > 1.0;
    if (CGSizeEqualToSize(self.nrgV55LastHostSize, size) &&
        self.nrgV55LastHostOrientation == orientation && !guestIsStale) return;
    self.nrgV55LastHostSize = size;
    self.nrgV55LastHostOrientation = orientation;
    __weak typeof(self) weakSelf = self;
    [self.appSceneVC updateFrameWithSettingsBlock:^(UIMutableApplicationSceneSettings *settings) {
        __strong typeof(weakSelf) strongSelf = weakSelf;
        if (strongSelf && strongSelf.isMaximized) {
            [strongSelf updateMaximizedFrameWithSettings:settings];
        }
    }];
    [self.view setNeedsLayout];
    [self.appSceneVC.view setNeedsLayout];
    NSLog(@"[NRG_V55_GEOMETRY] orientation=%ld host=%.1fx%.1f maximized=1",
          (long)orientation, size.width, size.height);
}

- (void)updateMaximizedFrameWithSettings:(UIMutableApplicationSceneSettings *)settings {
    UIWindow *window = self.view.window;
    if (!window || !self.view.superview || CGRectIsEmpty(window.bounds)) return;
    CGRect target = UIEdgeInsetsInsetRect(window.bounds,
                        [self updateMaximizedSafeAreaWithSettings:settings]);
    if (CGRectIsEmpty(target)) return;
    // Convert the window's current bounds into the hosting view's coordinates.
    target = [self.view.superview convertRect:target fromView:window];
    if (!CGRectEqualToRect(self.view.frame, target)) self.view.frame = target;
}"""
    return one(s,old,new,"maximized frame")

def dock(s):
    if MARK in s: return s
    begin=s.index("    // NRG_V53_ORIENTATION_RECONCILE: invalidate visible retained guest views.")
    end=s.index("    // NRG_V47_HOST_FOREGROUND_RESUME:",begin)
    new="""    // """+MARK+""": keep the overlay matched to the current host scene.
    @objc public func nrgV53ReconcileGuestGeometry(for hostScene: UIWindowScene) {
        precondition(Thread.isMainThread)
        if let parent = windowHostingView.superview,
           parent.window?.windowScene === hostScene,
           !parent.bounds.isEmpty, windowHostingView.frame != parent.bounds {
            windowHostingView.frame = parent.bounds
        }
        for app in apps {
            guard let view = app.view, !view.isHidden,
                  view.window?.windowScene === hostScene,
                  let controller = view._viewDelegate() as? DecoratedAppSceneViewController,
                  controller.appSceneVC.isAppRunning else { continue }
            // Preserve windowed guest position/size and intentional transforms.
            if controller.isMaximized {
                controller.nrgV55ReconcileRotationGeometry()
            }
            view.setNeedsLayout()
            controller.appSceneVC.view.setNeedsLayout()
        }
    }

"""
    return s[:begin]+new+s[end:]

def delegate(s):
    if MARK in s: return s
    old="            MultitaskDockManager.shared.nrgV47RestoreVisibleGuestScenes(for: windowScene)\n"
    new=old+"""            // """+MARK+""": restore geometry if rotation occurred while inactive.
            DispatchQueue.main.async {
                MultitaskDockManager.shared.nrgV53ReconcileGuestGeometry(for: windowScene)
            }
"""
    return one(s,old,new,"foreground recovery")

PATCHES=[
 ("MultitaskSupport/DecoratedAppSceneViewController.h",header),
 ("MultitaskSupport/DecoratedAppSceneViewController.m",decorated),
 ("MultitaskSupport/MultitaskDockView.swift",dock),
 ("LiveContainerSwiftUI/App/AppDelegate.swift",delegate)
]

def main(root):
    pending=[]
    for relative,patch in PATCHES:
        path=root/relative
        original=path.read_text()
        updated=patch(original)
        if patch(updated)!=updated: raise RuntimeError("non-idempotent "+relative)
        pending.append((path,original,updated))
    for path,original,updated in pending:
        if updated!=original: path.write_text(updated)
        print("[PASS] V55",path.relative_to(root))

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: patch_v55_rotation_geometry.py <LiveContainer>")
    main(Path(sys.argv[1]))
