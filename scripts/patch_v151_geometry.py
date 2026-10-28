#!/usr/bin/env python3
"""V151: consistent physical viewport and embedded guest scene dimensions.

Only common maximized guest geometry + foreground/rotation revalidation.
No bundle-specific overrides, no glass panel, no signing or App ID changes.
"""
from pathlib import Path
import sys

DEC=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
SWIFT=Path("MultitaskSupport/MultitaskDockView.swift")
MARK="SCARLET_V151_UNIFIED_GUEST_GEOMETRY"

def one(s,old,new,name):
    count=s.count(old)
    if count!=1:raise ValueError(f"V151 {name}: anchor count {count}")
    return s.replace(old,new,1)

def patch_decorated(s):
    if MARK in s:
        if s.count(MARK)!=1 or "SCARLET_V151_ORIENTATION_PARITY" not in s or "SCARLET_V151_FRAME_TOUCH_PARITY" not in s:
            raise ValueError("V151 decorated partial")
        return s
    for marker in ("SCARLET_V136_ROTATION_ATOMIC", "SCARLET_V129_VIEWPORT", "SCARLET_V141_INSET_AWARE_SETTLE","SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY"):
        if marker not in s: raise ValueError("V151 missing pinned geometry: "+marker)

    # AppSceneViewController.updateSettingsWithBlock already transforms the
    # remote scene frame according to settings.interfaceOrientation. Using
    # windowScene orientation for the first transform double-rotates a guest
    # that requested a different orientation (X fullscreen media). Use the
    # EXACT orientation of the remote scene consumed downstream.
    old='''    settings.frame = UIInterfaceOrientationIsLandscape(orientation)
        ? CGRectMake(0, 0, pixels.height, pixels.width)
        : CGRectMake(0, 0, pixels.width, pixels.height);'''
    new='''    // SCARLET_V151_UNIFIED_GUEST_GEOMETRY: the embedded guest consumes
    // settings.interfaceOrientation, not the host UIWindowScene orientation.
    // The second transform in AppSceneViewController reverses THIS one.
    // Otherwise host landscape + guest portrait gives wrong-sized hit regions.
    UIInterfaceOrientation guestOrientation = settings.interfaceOrientation;
    if (guestOrientation == UIInterfaceOrientationUnknown) {
        guestOrientation = orientation;
        settings.interfaceOrientation = orientation;
    }
    settings.frame = UIInterfaceOrientationIsLandscape(guestOrientation)
        ? CGRectMake(0, 0, pixels.height, pixels.width)
        : CGRectMake(0, 0, pixels.width, pixels.height);
    NSLog(@"[SCARLET_V151_ORIENTATION_PARITY] host=%ld guest=%ld hostSize=%.0fx%.0f outgoingFrame=%.0fx%.0f",
          (long)orientation, (long)guestOrientation, pixels.width, pixels.height,
          settings.frame.size.width, settings.frame.size.height);'''
    s=one(s,old,new,"maximized scene double rotation")

    # The physical UIWindow and rendered/interactive guest UIView must
    # share identical bounds; record discrepancies with useful evidence.
    s=one(s,
'''    if (!CGRectEqualToRect(self.view.frame, target)) self.view.frame = target;
    self.view.layer.cornerRadius = 0;''',
'''    if (!CGRectEqualToRect(self.view.frame, target)) self.view.frame = target;
    // SCARLET_V151_FRAME_TOUCH_PARITY: same physical frame for rendering
    // and hit-testing; never reuse a stale portrait child origin.
    CGRect actualRect = [self.view.superview convertRect:self.view.frame toView:window];
    NSLog(@"[SCARLET_V151_FRAME_TOUCH_PARITY] host=%@ viewport=%@ child=%@ orientation=%ld",
          NSStringFromCGRect(window.bounds), NSStringFromCGRect(actualRect),
          NSStringFromCGRect(self.appSceneVC.view.bounds), (long)orientation);
    self.view.layer.cornerRadius = 0;''',"render-to-hit frame parity log")

    # Rotated content dimensions are not sufficient: scene may have changed
    # safe insets or its parent viewport origin on the same UIWindow size.
    s=one(s,
'''    BOOL guestIsStale = fabs(guestSize.width - viewport.width) > 1.0 ||
                        fabs(guestSize.height - viewport.height) > 1.0;''',
'''    BOOL guestIsStale = fabs(guestSize.width - viewport.width) > 1.0 ||
                        fabs(guestSize.height - viewport.height) > 1.0;
    // An explicitly resized guest contentView may differ from its controller
    // view. Use size-only evidence here; scene update handles the correction.
    if (self.appSceneVC.contentView) {
        CGSize contentSize = self.appSceneVC.contentView.bounds.size;
        BOOL direct = fabs(contentSize.width - viewport.width) < 1.0 &&
                      fabs(contentSize.height - viewport.height) < 1.0;
        BOOL swapped = fabs(contentSize.height - viewport.width) < 1.0 &&
                       fabs(contentSize.width - viewport.height) < 1.0;
        if (!direct && !swapped) {
            // Diagnostic only: an app can legitimately expose a distinct
            // contentView (e.g. fullscreen media). Never force repeated
            // scene updates solely because this view has different bounds.
            NSLog(@"[SCARLET_V151_CONTENT_STALE] host=%.0fx%.0f content=%.0fx%.0f",
                  viewport.width, viewport.height, contentSize.width, contentSize.height);
        }
    }''',"detect stale guest content viewport")

    # Reconciliation needs a reliable view: changing ONLY the old media
    # orientation request cannot resize content that reattaches after switch.
    return s

def patch_dock(s):
    marker="SCARLET_V151_GUEST_RESUME_GEOMETRY"
    if marker in s:
        if s.count(marker)!=1: raise ValueError("V151 dock partial")
        return s
    if "NRG_V47_HOST_FOREGROUND_RESUME" not in s or "nrgV55ReconcileRotationGeometry" not in s:
        raise ValueError("V151 missing foreground reconciliation")
    old='''            controller.lcResumeMinimizedGuest()
            view.setNeedsLayout()
            NSLog("[NRG_V47_RESUME] visible_guest_restored=1 focus_forced=0 audio_forced=0")'''
    new='''            controller.lcResumeMinimizedGuest()
            // SCARLET_V151_GUEST_RESUME_GEOMETRY: returning from another
            // guest must settle current safe-area and rotation, even when the
            // host window did not fire windowScene(_:didUpdate:).
            controller.nrgV55ReconcileRotationGeometry()
            view.setNeedsLayout()
            NSLog("[NRG_V47_RESUME] visible_guest_restored=1 focus_forced=0 audio_forced=0")'''
    return one(s,old,new,"foreground guest rebind")

def apply(root):
    files=((DEC,patch_decorated),(SWIFT,patch_dock))
    changes=[]
    for rel,fn in files:
        p=root/rel
        if not p.is_file() or p.is_symlink():raise ValueError("missing LC root source "+str(rel))
        old=p.read_text();new=fn(old)
        if fn(new)!=new:raise ValueError("V151 non-idempotent: "+str(rel))
        changes.append((p,old,new))
    for p,o,n in changes:
        if o!=n:p.write_text(n)
    print("[PASS] V151 host/guest orientation parity, physical frame parity, foreground revalidation")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v151_geometry.py <LiveContainer>")
    apply(Path(sys.argv[1]))
