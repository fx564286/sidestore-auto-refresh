#!/usr/bin/env python3
"""V172 scene geometry: repair the one-way landscape coercion of V171.

Do NOT edit portrait safe-area math, app containers, identity, pairing, signing,
or the windowed guest path. Only undo a landscape orientation previously forced
by this controller when the physical host has committed portrait again.
Reconcile once through the same UIKit event path so changes are not timer-driven.
"""
from pathlib import Path
import sys

FILE=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK="SCARLET_V172_RESTORE_PORTRAIT"
OLD='''        if (hostCommittedLandscape &&
            UIInterfaceOrientationIsPortrait(settings.interfaceOrientation)) {
            settings.interfaceOrientation = hostOrientation;
            // The public interface and device orientation have opposite
            // left/right naming, as observed by UIKit.
            settings.deviceOrientation =
                hostOrientation == UIInterfaceOrientationLandscapeLeft
                    ? UIDeviceOrientationLandscapeRight : UIDeviceOrientationLandscapeLeft;
            NSLog(@"[SCARLET_V171_LANDSCAPE] stage=guest_orientation_sync host=%ld",
                  (long)hostOrientation);
        }'''
NEW='''        if (hostCommittedLandscape &&
            UIInterfaceOrientationIsPortrait(settings.interfaceOrientation)) {
            self.nrgV172LandscapeWasForced = YES;
            settings.interfaceOrientation = hostOrientation;
            settings.deviceOrientation =
                hostOrientation == UIInterfaceOrientationLandscapeLeft
                    ? UIDeviceOrientationLandscapeRight : UIDeviceOrientationLandscapeLeft;
            NSLog(@"[SCARLET_V171_LANDSCAPE] stage=guest_orientation_sync host=%ld",
                  (long)hostOrientation);
        } else if (self.nrgV172LandscapeWasForced && self.isMaximized &&
                   hostWindow && [self nrgV136GeometryStable:hostWindow] &&
                   UIInterfaceOrientationIsPortrait(hostOrientation) &&
                   CGRectGetHeight(hostWindow.bounds) > CGRectGetWidth(hostWindow.bounds) + 1.0) {
            // SCARLET_V172_RESTORE_PORTRAIT: V171's forced landscape must
            // never survive a return to physically committed portrait. This
            // branch exists ONLY when V171 previously forced the guest.
            settings.interfaceOrientation = hostOrientation;
            settings.deviceOrientation = hostOrientation == UIInterfaceOrientationPortraitUpsideDown
                ? UIDeviceOrientationPortraitUpsideDown : UIDeviceOrientationPortrait;
            self.nrgV172LandscapeWasForced = NO;
            NSLog(@"[SCARLET_V172_ORIENTATION] stage=restore_forced_guest_portrait");
        }'''
PROP='''@property(nonatomic) BOOL nrgV170LandscapeRepairAttempted;'''
CACHE='''    if (CGRectEqualToRect(measured, self.nrgV169LastMeasuredViewport) &&
        CGSizeEqualToSize(size, self.nrgV169LastMeasuredSize) &&
        UIEdgeInsetsEqualToEdgeInsets(insets, self.nrgV169LastMeasuredInsets) &&
        orientation == self.nrgV169LastMeasuredOrientation &&
        (!nrgV170LandscapeNeedsRepair || self.nrgV170LandscapeRepairAttempted)) return;'''
CACHE_NEW='''    BOOL nrgV172LandscapePromotionPending =
        !self.nrgV172LandscapeWasForced &&
        UIInterfaceOrientationIsLandscape(orientation) &&
        size.width > size.height + 1.0 &&
        UIInterfaceOrientationIsPortrait(self.appSceneVC.presenter.scene.settings.interfaceOrientation);
    BOOL nrgV172PortraitRestorePending =
        self.nrgV172LandscapeWasForced &&
        UIInterfaceOrientationIsPortrait(orientation) &&
        size.height > size.width + 1.0;
    if (CGRectEqualToRect(measured, self.nrgV169LastMeasuredViewport) &&
        CGSizeEqualToSize(size, self.nrgV169LastMeasuredSize) &&
        UIEdgeInsetsEqualToEdgeInsets(insets, self.nrgV169LastMeasuredInsets) &&
        orientation == self.nrgV169LastMeasuredOrientation &&
        (!nrgV170LandscapeNeedsRepair || self.nrgV170LandscapeRepairAttempted) &&
        !nrgV172PortraitRestorePending &&
        !nrgV172LandscapePromotionPending) return;'''
QUEUE='''        owner.nrgV169GeometryQueued = NO;
        // Never enter this branch in portrait. Repair at most once per stale'''
QUEUE_NEW='''        owner.nrgV169GeometryQueued = NO;
        UIWindow *settledWindow = owner.view.window;
        if (!owner.nrgV172LandscapeWasForced && owner.isMaximized &&
            settledWindow && [owner nrgV136GeometryStable:settledWindow] &&
            UIInterfaceOrientationIsLandscape(settledWindow.windowScene.interfaceOrientation) &&
            settledWindow.bounds.size.width > settledWindow.bounds.size.height + 1.0 &&
            UIInterfaceOrientationIsPortrait(owner.appSceneVC.presenter.scene.settings.interfaceOrientation)) {
            // UIKit settled landscape after the guest's previous callback.
            // Correct the retained portrait scene without waiting for a timer.
            owner.nrgV172LandscapeWasForced = YES;
            UIInterfaceOrientation committedLandscape = settledWindow.windowScene.interfaceOrientation;
            owner.appSceneVC.shouldSkipDebounceOnce = YES;
            [owner.appSceneVC updateFrameWithSettingsBlock:^(UIMutableApplicationSceneSettings *settings) {
                if (owner.isMaximized &&
                    UIInterfaceOrientationIsLandscape(owner.view.window.windowScene.interfaceOrientation)) {
                    settings.interfaceOrientation = committedLandscape;
                    settings.deviceOrientation =
                        committedLandscape == UIInterfaceOrientationLandscapeLeft
                            ? UIDeviceOrientationLandscapeRight : UIDeviceOrientationLandscapeLeft;
                    [owner updateMaximizedFrameWithSettings:settings];
                }
            }];
            NSLog(@"[SCARLET_V172_ORIENTATION] stage=layout_landscape_promote");
        }
        if (owner.nrgV172LandscapeWasForced && owner.isMaximized &&
            settledWindow && [owner nrgV136GeometryStable:settledWindow] &&
            UIInterfaceOrientationIsPortrait(settledWindow.windowScene.interfaceOrientation) &&
            CGRectGetHeight(settledWindow.bounds) > CGRectGetWidth(settledWindow.bounds) + 1.0) {
            // The guest need not emit a second didUpdateFromSettings on host
            // rotation, so resolve the V171-forced orientation on UIKit layout.
            // Do not change the physical portrait safe-area calculation.
            owner.nrgV172LandscapeWasForced = NO;
            owner.appSceneVC.shouldSkipDebounceOnce = YES;
            UIInterfaceOrientation settledPortrait = settledWindow.windowScene.interfaceOrientation;
            [owner.appSceneVC updateFrameWithSettingsBlock:^(UIMutableApplicationSceneSettings *settings) {
                if (owner.isMaximized &&
                    UIInterfaceOrientationIsPortrait(owner.view.window.windowScene.interfaceOrientation)) {
                    settings.interfaceOrientation = settledPortrait;
                    settings.deviceOrientation =
                        settledPortrait == UIInterfaceOrientationPortraitUpsideDown
                            ? UIDeviceOrientationPortraitUpsideDown : UIDeviceOrientationPortrait;
                    [owner updateMaximizedFrameWithSettings:settings];
                }
            }];
            NSLog(@"[SCARLET_V172_ORIENTATION] stage=layout_portrait_restore");
        }
        // Never enter this branch in portrait. Repair at most once per stale'''
def once(s,a,b,label):
    if s.count(a)!=1:raise ValueError(f"V172 {label}: expected one anchor, got {s.count(a)}")
    return s.replace(a,b,1)

def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or "nrgV172PortraitRestorePending" not in s or "nrgV172LandscapePromotionPending" not in s:raise ValueError("V172 partial patch")
        return s
    for need in ("SCARLET_V171_LANDSCAPE_SCENE_FRAME","SCARLET_V170_LANDSCAPE_ONLY",
                 "SCARLET_V169_EVENT_DRIVEN_VIEWPORT","SCARLET_V151_UNIFIED_GUEST_GEOMETRY"):
        if need not in s:raise ValueError("V172 missing prerequisite "+need)
    s=once(s,PROP,PROP+"\n// Restore V171's forced landscape on committed portrait only.\n@property(nonatomic) BOOL nrgV172LandscapeWasForced;","state")
    s=once(s,OLD,NEW,"orientation")
    s=once(s,CACHE,CACHE_NEW,"cache")
    s=once(s,QUEUE,QUEUE_NEW,"event-driven restore")
    return s

def main(root):
    p=root/FILE
    if not p.is_file() or p.is_symlink():raise ValueError("V172 pinned guest source missing")
    old=p.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:raise ValueError("V172 non-idempotent")
    if new!=old:p.write_text(new,encoding="utf-8")
    print("[PASS] V172 portrait restoration only after V171 forced landscape")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v172_scene_restore.py <LiveContainer>")
    main(Path(sys.argv[1]))
