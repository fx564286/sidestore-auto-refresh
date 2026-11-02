#!/usr/bin/env python3
"""V175 fixes stale UIKit constraints and asymmetric media scene rotation.

The pinned DecoratedAppSceneViewController updates the guest scene *before*
activating new constraints. On iOS 27 the hosted LiveProcess renderer then
gets the previous dimensions. Move the one update after constraint layout.
Restore portrait geometry requests to the same guarded path as landscape.
No app-specific hooks, container writes, signed-identity or pairing changes.
"""
from pathlib import Path
import sys

SOURCE = Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK_LAYOUT = "SCARLET_V175_LAYOUT_BEFORE_GUEST_COMMIT"
MARK_MEDIA = "SCARLET_V175_SYMMETRIC_MEDIA_GEOMETRY"

OLD_EARLY = '''        // Update safe area insets
        if(self.isMaximized) {
            self.appSceneVC.shouldSkipDebounceOnce = YES;
            __weak typeof(self) weakSelf = self;
            [self.appSceneVC updateSettingsWithBlock:^(UIMutableApplicationSceneSettings *settings) {
                [weakSelf updateMaximizedFrameWithSettings:settings];
            }];
        }
        
        [NSLayoutConstraint deactivateConstraints:self.activatedVerticalConstraints];'''

NEW_EARLY = '''        // SCARLET_V175_LAYOUT_BEFORE_GUEST_COMMIT: the old path published
        // stale portrait constraints before the new guest viewport existed.
        // Commit constraints, settle the layout, THEN update guest geometry.
        [NSLayoutConstraint deactivateConstraints:self.activatedVerticalConstraints];'''

OLD_LATE = '''        [NSLayoutConstraint activateConstraints:self.activatedVerticalConstraints];

        [self.view layoutIfNeeded];
    }];
}'''

NEW_LATE = '''        [NSLayoutConstraint activateConstraints:self.activatedVerticalConstraints];

        [self.view layoutIfNeeded];
        if (self.isMaximized && self.view.window) {
            // Reconcile against the new constrained content dimensions. This
            // method runs only when a window bar's layout actually changes.
            self.appSceneVC.shouldSkipDebounceOnce = YES;
            __weak typeof(self) weakSelf = self;
            [self.appSceneVC updateFrameWithSettingsBlock:^(UIMutableApplicationSceneSettings *settings) {
                __strong typeof(weakSelf) owner = weakSelf;
                if (owner && owner.isMaximized && owner.view.window)
                    [owner updateMaximizedFrameWithSettings:settings];
            }];
            NSLog(@"[SCARLET_V175_LAYOUT] stage=constraints_committed viewport=%.0fx%.0f guest=%.0fx%.0f",
                  self.view.bounds.size.width, self.view.bounds.size.height,
                  self.appSceneVC.view.bounds.size.width,
                  self.appSceneVC.view.bounds.size.height);
        }
    }];
}'''

MEDIA_START = "- (void)nrgV139RequestGuestVideoOrientation:(UIInterfaceOrientation)requested {"
MEDIA_END = "\n- (void)appSceneVC:(AppSceneViewController*)vc didUpdateFromSettings:"

MEDIA_METHOD = '''// SCARLET_V175_SYMMETRIC_MEDIA_GEOMETRY: a guest's explicit full-screen
// orientation is considered for both landscape and portrait. Never rotate
// the phone unless physical UIDevice orientation agrees with the request.
- (void)nrgV139RequestGuestVideoOrientation:(UIInterfaceOrientation)requested {
    if (!self.isMaximized || !self.appSceneVC.isAppRunning || self.view.hidden) return;
    UIWindow *window = self.view.window;
    UIWindowScene *scene = window.windowScene;
    if (!scene || scene.activationState != UISceneActivationStateForegroundActive) return;
    BOOL portrait = UIInterfaceOrientationIsPortrait(requested);
    BOOL landscape = UIInterfaceOrientationIsLandscape(requested);
    if ((!portrait && !landscape) || scene.interfaceOrientation == requested) {
        self.nrgV139LastVideoOrientation = UIInterfaceOrientationUnknown;
        return;
    }
    // The previous V139 implementation only requested landscape, so a
    // fullscreen media transition back to portrait could leave the host
    // landscape while its actual remote content was already portrait.
    UIDeviceOrientation physical = UIDevice.currentDevice.orientation;
    if ((portrait && !UIDeviceOrientationIsPortrait(physical)) ||
        (landscape && !UIDeviceOrientationIsLandscape(physical))) {
        NSLog(@"[SCARLET_V175_MEDIA] stage=defer reason=physical_orientation_mismatch");
        return;
    }
    CFAbsoluteTime now = CFAbsoluteTimeGetCurrent();
    if (self.nrgV139LastVideoOrientation == requested &&
        now - self.nrgV139LastVideoOrientationRequest < 1.5) return;
    if (@available(iOS 16.0, *)) {
        UIInterfaceOrientationMask mask = UIInterfaceOrientationMaskPortrait;
        switch (requested) {
            case UIInterfaceOrientationPortrait:
                mask = UIInterfaceOrientationMaskPortrait; break;
            case UIInterfaceOrientationPortraitUpsideDown:
                mask = UIInterfaceOrientationMaskPortraitUpsideDown; break;
            case UIInterfaceOrientationLandscapeLeft:
                mask = UIInterfaceOrientationMaskLandscapeLeft; break;
            case UIInterfaceOrientationLandscapeRight:
                mask = UIInterfaceOrientationMaskLandscapeRight; break;
            default: return;
        }
        self.nrgV139LastVideoOrientation = requested;
        self.nrgV139LastVideoOrientationRequest = now;
        UIWindowSceneGeometryPreferencesIOS *preference =
            [[UIWindowSceneGeometryPreferencesIOS alloc] initWithInterfaceOrientations:mask];
        __weak typeof(self) weakSelf = self;
        [scene requestGeometryUpdateWithPreferences:preference errorHandler:^(NSError *error) {
            NSLog(@"[SCARLET_V175_MEDIA] stage=request_rejected code=%ld", (long)error.code);
            __strong typeof(weakSelf) owner = weakSelf;
            if (owner && owner.view.window) [owner.view setNeedsLayout];
        }];
        NSLog(@"[SCARLET_V175_MEDIA] stage=requested desired=%ld host=%ld",
              (long)requested, (long)scene.interfaceOrientation);
    }
}
'''

def one(s, old, new, label):
    count = s.count(old)
    if count != 1:
        raise ValueError("V175 %s: expected one anchor, found %d" % (label, count))
    return s.replace(old, new, 1)

def patch(s):
    if MARK_LAYOUT in s or MARK_MEDIA in s:
        if s.count(MARK_LAYOUT)!=1 or s.count(MARK_MEDIA)!=1 or \
           "stage=constraints_committed" not in s or "UIInterfaceOrientationMaskPortrait" not in s:
            raise ValueError("V175 incomplete source modification")
        return s
    for token in ("SCARLET_V174_BOUNDED_GEOMETRY",
                  "SCARLET_V173_SINGLE_SCENE_GEOMETRY_OWNER",
                  "SCARLET_V151_ORIENTATION_PARITY",
                  "SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY",
                  "NRG_V64_PORTRAIT_TOUCH_FRAME"):
        if token not in s:
            raise ValueError("V175 missing prior verified source marker "+token)
    beg=s.index("- (void)updateVerticalConstraints {")
    end=s.index("\n- (UIEdgeInsets)updateMaximizedSafeAreaWithSettings:",beg)
    method=s[beg:end]
    method=one(method,OLD_EARLY,NEW_EARLY,"early stale settings transaction")
    method=one(method,OLD_LATE,NEW_LATE,"new committed constraints transaction")
    s=s[:beg]+method+s[end:]
    if s.count(MEDIA_START)!=1 or s.count(MEDIA_END)!=1:
        raise ValueError("V175 duplicated or missing guest media callback")
    a=s.index(MEDIA_START)
    b=s.index(MEDIA_END,a)
    previous=s[a:b]
    if "SCARLET_V139_VIDEO" not in previous or "requestGeometryUpdateWithPreferences" not in previous:
        raise ValueError("V175 obsolete callback no longer has audited orientation path")
    s=s[:a]+MEDIA_METHOD+s[b:]
    if s.count(MARK_LAYOUT)!=1 or s.count(MARK_MEDIA)!=1:
        raise ValueError("V175 source patch incomplete")
    return s

def apply(root):
    p=root/SOURCE
    if not p.is_file() or p.is_symlink():
        raise ValueError("V175 pinned LiveContainer source missing")
    old=p.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:
        raise ValueError("V175 non-idempotent")
    if old!=new:
        p.write_text(new,encoding="utf-8")
    print("[PASS] V175 layout commits before scene settings; guest media portrait/landscape symmetric")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v175_layout_media.py <LiveContainer>")
    apply(Path(sys.argv[1]))
