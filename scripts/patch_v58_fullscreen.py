#!/usr/bin/env python3
"""V58: real guest viewport fills the host window in portrait AND landscape.

The system Dynamic Island and home gesture remain system-owned; guest *content*
may use UIKit-reported safeAreaInsets without shrinking the displayed guest
window. Fixes stale settings.frame when V55 callback resized after its read.
Requires pinned LiveContainer with V36/V38/V55 patches.
"""
from pathlib import Path
import sys

MARK="NRG_V58_EDGE_TO_EDGE_GUEST"
DECORATED=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
DOCK=Path("MultitaskSupport/MultitaskDockView.swift")

def one(s, old, new, what):
    if s.count(old)!=1:raise RuntimeError(f"V58 {what}: expected exactly 1 anchor, got {s.count(old)}")
    return s.replace(old,new,1)

def decorated(s):
    if MARK in s:
        if s.count(MARK)!=4 or "settings.frame = CGRectMake" not in s:
            raise RuntimeError("partial V58 decorated fullscreen")
        return s
    for dep in ("NRG_V36_MAXIMIZED_GUEST_CHROME",
                "NRG_V38_MAXIMIZED_SAFE_AREA_FRAME",
                "NRG_V55_ROTATION_GEOMETRY"):
        if dep not in s:raise RuntimeError("V58 requires "+dep)
    s=one(s,
       '_isMaximized = [NSUserDefaults.lcUserDefaults boolForKey:@"LCLaunchMultitaskMaximized"];',
       '''// '''+MARK+''': iPhone guest launches fullscreen by default; explicit
    // window-management controls still allow returning to a floating window.
    // Leave iPad window preferences unchanged.
    _isMaximized = UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPhone
        ? YES : [NSUserDefaults.lcUserDefaults boolForKey:@"LCLaunchMultitaskMaximized"];''',
       "phone launch default")
    s=one(s,
       '''    self.view.layer.cornerRadius = 10;
    self.view.layer.masksToBounds = YES;''',
       '''    // '''+MARK+''': never clip the full-screen guest into a round rectangle.
    self.view.layer.cornerRadius = _isMaximized ? 0 : 10;
    self.view.layer.masksToBounds = !_isMaximized;''',
       "edge clipping")
    s=one(s,
       '''    if(self.navigationBar.hidden) {
        // NRG_V38_MAXIMIZED_SAFE_AREA_FRAME: the hidden host bar must not
        // let the guest's interactive content extend behind Dynamic Island.
        // Inset the actual host frame, not merely the SwiftUI visual scale.
        // Avoid double-applying the same top inset through peripheryInsets.
        settings.peripheryInsets = UIEdgeInsetsMake(0, safeAreaInsets.left,
                                                   safeAreaInsets.bottom, safeAreaInsets.right);''',
       '''    if(self.navigationBar.hidden) {
        // '''+MARK+''': draw guest pixels across the *whole* screen. Safe-area
        // guidance goes to the guest scene only, not to the host view's frame.
        settings.peripheryInsets = UIEdgeInsetsZero;
        // NRG_V196_PORTRAIT_TOUCH_SAFEAREA: the maximized guest frame is
        // deliberately edge-to-edge, so its own safeAreaInsets can be zero.
        // Obtain system exclusion insets from the UIWindow instead. Forward
        // them to the guest scene so UIKit places interactive controls below
        // the status bar / Dynamic Island and above the home gesture.
        UIWindow *guestWindow = self.view.window;
        UIInterfaceOrientation guestOrientation = guestWindow.windowScene.interfaceOrientation;
        UIEdgeInsets guestSafeInsets = safeAreaInsets;
        if (guestWindow && UIInterfaceOrientationIsPortrait(guestOrientation)) {
            UIEdgeInsets systemInsets = guestWindow.safeAreaInsets;
            guestSafeInsets.top = MAX(guestSafeInsets.top, systemInsets.top);
            guestSafeInsets.bottom = MAX(guestSafeInsets.bottom, systemInsets.bottom);
            guestSafeInsets.left = MAX(guestSafeInsets.left, systemInsets.left);
            guestSafeInsets.right = MAX(guestSafeInsets.right, systemInsets.right);
        }
        settings.safeAreaInsetsPortrait = LCUIEdgeInsetsRotateToOrientation(
            guestSafeInsets, guestOrientation);
        NSLog(@"[NRG_V196_PORTRAIT_SAFEAREA] orientation=%ld top=%.1f bottom=%.1f windowTop=%.1f windowBottom=%.1f",
              (long)guestOrientation, guestSafeInsets.top, guestSafeInsets.bottom,
              guestWindow.safeAreaInsets.top, guestWindow.safeAreaInsets.bottom);
        return UIEdgeInsetsZero;''',
       "maximized fullscreen safe area")
    old='''    CGRect target = UIEdgeInsetsInsetRect(window.bounds,
                        [self updateMaximizedSafeAreaWithSettings:settings]);
    if (CGRectIsEmpty(target)) return;
    // Convert the window's current bounds into the hosting view's coordinates.
    target = [self.view.superview convertRect:target fromView:window];
    if (!CGRectEqualToRect(self.view.frame, target)) self.view.frame = target;'''
    new='''    // '''+MARK+''': UIKit window bounds are the only full-screen authority.
    // NRG_V64_PORTRAIT_TOUCH_FRAME: the previous edge-to-edge *scene*
    // frame put interactive guest controls beneath the hardware Island. Some
    // guest apps ignore settings.safeAreaInsetsPortrait, so they remain
    // inaccessible despite V196. Only portrait iPhone uses a physically
    // touch-safe viewport. Leave landscape and iPad frames untouched.
    [self updateMaximizedSafeAreaWithSettings:settings];
    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    BOOL portraitPhone = UIDevice.currentDevice.userInterfaceIdiom == UIUserInterfaceIdiomPhone &&
        UIInterfaceOrientationIsPortrait(orientation);
    CGRect physicalRect = window.bounds;
    CGFloat portraitTop = 0.0;
    CGFloat portraitBottom = 0.0;
    if (portraitPhone) {
        UIEdgeInsets physicalInsets = window.safeAreaInsets;
        portraitTop = MAX(physicalInsets.top, self.view.superview.safeAreaInsets.top);
        portraitBottom = MAX(physicalInsets.bottom, self.view.superview.safeAreaInsets.bottom);
        // The status bar may be hidden in a retained guest window. Use the
        // scene's status frame when available, never a translated child frame.
        UIStatusBarManager *statusManager = window.windowScene.statusBarManager;
        if (statusManager) {
            portraitTop = MAX(portraitTop, CGRectGetMaxY(statusManager.statusBarFrame));
        }
        // iOS 26/27 can report zero insets for borderless hosted scenes.
        // A conservative fallback applies only to modern portrait phones.
        if (@available(iOS 26.0, *)) {
            if (portraitTop < 32.0) portraitTop = 59.0;
            if (portraitBottom < 10.0) portraitBottom = 34.0;
        }
        portraitTop = MIN(MAX(portraitTop, 0.0), CGRectGetHeight(physicalRect) / 4.0);
        portraitBottom = MIN(MAX(portraitBottom, 0.0), CGRectGetHeight(physicalRect) / 5.0);
        // NRG_V70_PORTRAIT_BOTTOM_BLEED: keep the proven physical TOP guard
        // protecting notch controls, but let the guest paint right through
        // the home-indicator strip. Cutting the bottom 34pt off the actual
        // guest UIView exposed the underlying LiveContainer window chrome.
        // UIKit guest controls still receive the home-gesture exclusion via
        // scene safe-area metadata. No bottom physical inset AND metadata
        // inset at once; no changes to the landscape/iPad code path.
        physicalRect = UIEdgeInsetsInsetRect(physicalRect,
            UIEdgeInsetsMake(portraitTop, 0, 0, 0));
        settings.safeAreaInsetsPortrait = LCUIEdgeInsetsRotateToOrientation(
            UIEdgeInsetsMake(0, 0, portraitBottom, 0), orientation);
        settings.peripheryInsets = UIEdgeInsetsZero;
    }
    if (CGRectIsEmpty(physicalRect)) return;
    // Convert from UIWindow to the actual hosting superview: its origin can
    // be offset by the V3 SwiftUI safe area and must not be subtracted twice.
    CGRect target = [self.view.superview convertRect:physicalRect fromView:window];
    if (!CGRectEqualToRect(self.view.frame, target)) self.view.frame = target;
    self.view.layer.cornerRadius = 0;
    self.view.layer.masksToBounds = NO;
    // Scene pixels and hit-test viewport share identical physical bounds.
    // The landscape orientation swap remains exactly as in V58.
    CGSize pixels = physicalRect.size;
    settings.frame = UIInterfaceOrientationIsLandscape(orientation)
        ? CGRectMake(0, 0, pixels.height, pixels.width)
        : CGRectMake(0, 0, pixels.width, pixels.height);
    NSLog(@"[NRG_V64_PORTRAIT_TOUCH_FRAME] orientation=%ld full=%d top=%.1f bottom=%.1f window=%.0fx%.0f viewport=%.0fx%.0f viewY=%.1f",
          (long)orientation, portraitPhone ? 1 : 0, portraitTop, portraitBottom,
          window.bounds.size.width, window.bounds.size.height,
          pixels.width, pixels.height, self.view.frame.origin.y);
    NSLog(@"[NRG_V58_VIEWPORT] orientation=%ld window=%.0fx%.0f guest=%.0fx%.0f full=1",
          (long)orientation, window.bounds.size.width, window.bounds.size.height,
          self.view.bounds.size.width, self.view.bounds.size.height);'''
    s=one(s,old,new,"V55 host container frame")
    return s

def dock(s):
    if "NRG_V58_HOST_WINDOW_GEOMETRY" in s:
        if s.count("NRG_V58_HOST_WINDOW_GEOMETRY")!=1:raise RuntimeError("partial V58 dock")
        return s
    old='''           !parent.bounds.isEmpty, windowHostingView.frame != parent.bounds {
            windowHostingView.frame = parent.bounds
        }'''
    new='''           !parent.bounds.isEmpty {
            // NRG_V58_HOST_WINDOW_GEOMETRY: the parent may be a SwiftUI safe-
            // area child; its bounds are not necessarily the full UIWindow.
            let hostRect = parent.convert(hostScene.windows.first(where: {
                $0.isKeyWindow
            })?.bounds ?? hostScene.coordinateSpace.bounds,
                from: parent.window)
            if !hostRect.isEmpty && windowHostingView.frame != hostRect {
                windowHostingView.frame = hostRect
            }
        }'''
    return one(s,old,new,"dock virtual host coordinate conversion")

def main(root):
    patches=((DECORATED,decorated),(DOCK,dock))
    pending=[]
    for relative,patch in patches:
        p=root/relative
        before=p.read_text()
        after=patch(before)
        if patch(after)!=after:raise RuntimeError("V58 transform not idempotent: "+str(relative))
        pending.append((p,before,after))
    for p, before, after in pending:
        if before!=after:p.write_text(after)
        print("[PASS] V58 fullscreen",p.relative_to(root))

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v58_fullscreen.py <LiveContainer>")
    main(Path(sys.argv[1]))
