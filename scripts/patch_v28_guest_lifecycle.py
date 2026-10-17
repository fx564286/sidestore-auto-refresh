#!/usr/bin/env python3
"""V28: synchronize virtual guest focus, scene activation and home audio lifecycle.

Apply after V27 guest-switch patch to pinned LiveContainer sources.
No guest process is terminated, no global AVAudioSession is modified, and
PiP scenes remain foreground to preserve legitimate PiP playback.
"""
from pathlib import Path
import sys

MARKER = "NRG_V28_GUEST_LIFECYCLE"

APP_M = "MultitaskSupport/AppSceneViewController.m"
APP_H = "MultitaskSupport/AppSceneViewController.h"
DEC_M = "MultitaskSupport/DecoratedAppSceneViewController.m"
DEC_H = "MultitaskSupport/DecoratedAppSceneViewController.h"
DOCK = "MultitaskSupport/MultitaskDockView.swift"


def once(src: str, old: str, new: str, where: str) -> str:
    n = src.count(old)
    if n != 1:
        raise SystemExit(f"[FAIL] {where} has {n} pinned anchors")
    return src.replace(old, new, 1)


def patch(root: Path) -> None:
    paths = [root / p for p in (APP_M, APP_H, DEC_M, DEC_H, DOCK)]
    sources = [p.read_text(encoding="utf-8") for p in paths]
    if all(MARKER in s for s in sources):
        if any(s.count(MARKER) != 1 for s in sources):
            raise SystemExit("Partial or duplicate V28 guest lifecycle")
        print("[PASS] V28 guest lifecycle already applied")
        return
    if any(MARKER in s for s in sources):
        raise SystemExit("[FAIL] Incomplete V28 guest lifecycle")
    app, ah, dec, dh, dock = sources
    if "NRG_V27_GUEST_SWITCH_LIFECYCLE" not in dock:
        raise SystemExit("[FAIL] V27 guest lifecycle missing")

    ah = once(ah,
        "- (void)setBackgroundNotificationEnabled:(bool)enabled;\n",
        """// NRG_V28_GUEST_LIFECYCLE: virtual scene visibility, independent of PiP observers.
- (void)lcSetGuestSceneForeground:(BOOL)foreground;
- (void)setBackgroundNotificationEnabled:(bool)enabled;
""", APP_H)

    # Scene activation is what allows the remote LiveProcess UIKit scene to
    # relinquish focus and stop foreground-only audio. Do not touch the global
    # audio session or send signals to the guest PID.
    app = once(app, "- (void)setBackgroundNotificationEnabled:(bool)enabled {\n",
        """// NRG_V28_GUEST_LIFECYCLE: virtual minimization is not app termination.
- (void)lcSetGuestSceneForeground:(BOOL)foreground {
    if (!self.isAppRunning || !self.presenter) return;
    if (!NSThread.isMainThread) {
        dispatch_async(dispatch_get_main_queue(), ^{ [self lcSetGuestSceneForeground:foreground]; });
        return;
    }
    if (!foreground) {
        [self.contentView endEditing:YES];
        [self.view endEditing:YES];
    }
    [self.presenter.scene updateSettingsWithBlock:^(UIMutableApplicationSceneSettings *settings) {
        settings.foreground = foreground;
        if (foreground) settings.deactivationReasons = 0;
    }];
    NSLog(@"[NRG_V28_GUEST_SCENE] foreground=%d", foreground ? 1 : 0);
}

- (void)setBackgroundNotificationEnabled:(bool)enabled {
""", APP_M)

    dh = once(dh, "- (void)minimizeWindow;\n",
        """// NRG_V28_GUEST_LIFECYCLE: restore the retained remote scene on activation.
- (void)lcResumeMinimizedGuest;
- (void)minimizeWindow;
""", DEC_H)

    old = """- (void)minimizeWindow {
    if (self.view.hidden) return;
    [UIView animateWithDuration:0.3 delay:0 options:UIViewAnimationOptionCurveEaseInOut animations:^{
        self.view.alpha = 0;
        self.view.transform = CGAffineTransformMakeScale(0.1, 0.1);
    } completion:^(BOOL finished) {
        if (!finished) return;
        self.view.hidden = YES;
        self.view.transform = CGAffineTransformIdentity;
        [self.view.superview sendSubviewToBack:self.view];
    }];
}
"""
    new = """// NRG_V28_GUEST_LIFECYCLE: avoid 0.1-scale geometry races and background
// the actual remote scene before returning to the host. PiP is exempt.
- (void)lcResumeMinimizedGuest {
    if (!self.appSceneVC.isAppRunning) return;
    [self.appSceneVC lcSetGuestSceneForeground:YES];
}

- (void)minimizeWindow {
    if (self.view.hidden) return;
    [self.view endEditing:YES];
    [self.appSceneVC.view endEditing:YES];
    [self.appSceneVC.contentView endEditing:YES];
    [self.view.window endEditing:YES];
    if (![PiPManager.shared isPiPWithVC:self.appSceneVC]) {
        [self.appSceneVC lcSetGuestSceneForeground:NO];
    }
    [self.view.layer removeAllAnimations];
    self.view.transform = CGAffineTransformIdentity;
    [UIView animateWithDuration:0.3 delay:0
                        options:UIViewAnimationOptionCurveEaseInOut | UIViewAnimationOptionBeginFromCurrentState
                     animations:^{
        self.view.alpha = 0;
    } completion:^(BOOL finished) {
        if (!finished) return;
        self.view.hidden = YES;
        [self.view.superview sendSubviewToBack:self.view];
    }];
}
"""
    dec = once(dec, old, new, DEC_M)
    dock = once(dock,
        """            old.endEditing(true)
            if let vc = old._viewDelegate() as? DecoratedAppSceneViewController {
                vc.appSceneVC.view.endEditing(true)
            }
""",
        """            // NRG_V28_GUEST_LIFECYCLE: close remote responder and background old scene.
            old.endEditing(true)
            if let vc = old._viewDelegate() as? DecoratedAppSceneViewController {
                vc.appSceneVC.view.endEditing(true)
                vc.appSceneVC.contentView?.endEditing(true)
                if PiPManager.shared?.isPiP(withDecoratedVC: vc) != true {
                    vc.appSceneVC.lcSetGuestSceneForeground(false)
                }
            }
""", DOCK + " old guest")
    dock = once(dock,
        """        bringViewToFront(view, in: window)
        // Preserve windowed/maximized frame and the user's chosen scale.
""",
        """        controller?.lcResumeMinimizedGuest()
        bringViewToFront(view, in: window)
        // Preserve windowed/maximized frame and the user's chosen scale.
""", DOCK + " resume")

    outputs = [app, ah, dec, dh, dock]
    if any(s.count(MARKER) != 1 for s in outputs):
        raise SystemExit("[FAIL] V28 lifecycle marker validation")
    for p, s in zip(paths, outputs):
        p.write_text(s, encoding="utf-8")
    print("[PASS] V28 remote keyboard focus, guest scene visibility, home audio background and PiP protection")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v28_guest_lifecycle.py <LiveContainer>")
    patch(Path(sys.argv[1]))
