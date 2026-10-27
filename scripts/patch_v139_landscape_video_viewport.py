#!/usr/bin/env python3
"""V139: prevent hosted fullscreen-video landscape viewport regression.

A guest orientation callback currently recomputes the correct edge-to-edge
frame, then overwrites it with an obsolete pre-layout frame. Preserve V136's
physical HWND UIWindow geometry and ask UIKit for host orientation only when
an active maximized guest actually requests landscape. No guest/signed data
changes, no forced orientation if UIKit refuses the request.
"""
from pathlib import Path
import sys

SOURCE=Path('MultitaskSupport/DecoratedAppSceneViewController.m')
MARK='SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY'


def one(s,a,b,label):
    n=s.count(a)
    if n!=1:raise ValueError(f'V139 landscape {label}: expected 1 anchor, found {n}')
    return s.replace(a,b,1)


def decorated(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'nrgV139RequestGuestVideoOrientation:' not in s:
            raise ValueError('partial landscape guest patch')
        return s
    for marker in ('SCARLET_V136_ROTATION_ATOMIC', 'NRG_V58_EDGE_TO_EDGE_GUEST',
                   'NRG_V55_ROTATION_GEOMETRY','SCARLET_V129_JIT_VIEWPORT'):
        if marker not in s:raise ValueError('V139 missing fullscreen prerequisite '+marker)
    # Guest media's orientation must request host geometry independently of
    # retained scene frame callbacks, otherwise the host remains portrait
    # with clipped black bars revealing the SwiftUI home to left and right.
    anchor='''- (void)appSceneVC:(AppSceneViewController*)vc didUpdateFromSettings:(UIMutableApplicationSceneSettings *)baseSettings transitionContext:(id)newContext lifecycleActionType:(uint32_t)actionType {'''
    replacement='''// SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY: use the actual guest orientation
// on media fullscreen transitions. Never coerce a portrait-only external app.
- (void)nrgV139RequestGuestVideoOrientation:(UIInterfaceOrientation)requested {
    if (!self.isMaximized || !self.appSceneVC.isAppRunning || self.view.hidden) return;
    UIWindowScene *scene = self.view.window.windowScene;
    if (!scene || scene.activationState != UISceneActivationStateForegroundActive) return;
    if (!UIInterfaceOrientationIsLandscape(requested) ||
        scene.interfaceOrientation == requested) return;
    if (@available(iOS 16.0, *)) {
        UIDeviceOrientation device = UIDevice.currentDevice.orientation;
        // Do not rotate the user's phone just because an embedded UI emitted
        // a stale orientation while the physical device remains upright.
        if (!UIDeviceOrientationIsLandscape(device)) {
            NSLog(@"[SCARLET_V139_VIDEO] orientation=request_skipped reason=device_not_landscape");
            return;
        }
        UIInterfaceOrientationMask mask = requested == UIInterfaceOrientationLandscapeRight
            ? UIInterfaceOrientationMaskLandscapeRight : UIInterfaceOrientationMaskLandscapeLeft;
        UIWindowSceneGeometryPreferencesIOS *preferences =
            [[UIWindowSceneGeometryPreferencesIOS alloc] initWithInterfaceOrientations:mask];
        __weak typeof(self) weakSelf = self;
        [scene requestGeometryUpdateWithPreferences:preferences errorHandler:^(NSError *error) {
            NSLog(@"[SCARLET_V139_VIDEO] orientation=request_rejected code=%ld", (long)error.code);
            __strong typeof(weakSelf) owner = weakSelf;
            if (owner) [owner.view setNeedsLayout];
        }];
        NSLog(@"[SCARLET_V139_VIDEO] orientation=requested guest=%ld current=%ld",
              (long)requested, (long)scene.interfaceOrientation);
    }
}

- (void)appSceneVC:(AppSceneViewController*)vc didUpdateFromSettings:(UIMutableApplicationSceneSettings *)baseSettings transitionContext:(id)newContext lifecycleActionType:(uint32_t)actionType {'''
    s=one(s,anchor,replacement,'host scene geometry request on guest orientation')
    # In the existing method updateMaximizedFrameWithSettings() already sets
    # the authoritative frame, but the legacy final recalculation overwrites it.
    obsolete='''        CGRect newFrame = CGRectMake(0, 0, self.view.bounds.size.width, self.view.bounds.size.height - self.navigationBar.frame.size.height/self.scaleRatio);
        
        if(UIInterfaceOrientationIsLandscape(baseSettings.interfaceOrientation)) {
            settings.frame = CGRectMake(0, 0, newFrame.size.height, newFrame.size.width);
        } else {
            settings.frame = CGRectMake(0, 0, newFrame.size.width, newFrame.size.height);
        }'''
    corrected='''        // Maximize() has already published the atomic physical viewport.
        // A second settings.frame write here used the OLD portrait view size,
        // producing exposed LiveContainer stripes during fullscreen video.
        if (!self.isMaximized) {
            CGRect newFrame = CGRectMake(0, 0, self.view.bounds.size.width,
                self.view.bounds.size.height - self.navigationBar.frame.size.height / self.scaleRatio);
            settings.frame = UIInterfaceOrientationIsLandscape(baseSettings.interfaceOrientation)
                ? CGRectMake(0, 0, newFrame.size.height, newFrame.size.width)
                : CGRectMake(0, 0, newFrame.size.width, newFrame.size.height);
        }'''
    s=one(s,obsolete,corrected,'remove duplicate maximized-frame override')
    # Request host orientation outside updateSettingsWithBlock (no nested
    # scene mutation while another guest update is being committed).
    s=one(s,
        '''    [self.appSceneVC updateSettingsWithBlock:^(UIMutableApplicationSceneSettings *settings) {
        settings.userInterfaceStyle = baseSettings.userInterfaceStyle;''',
        '''    [self nrgV139RequestGuestVideoOrientation:baseSettings.interfaceOrientation];
    [self.appSceneVC updateSettingsWithBlock:^(UIMutableApplicationSceneSettings *settings) {
        settings.userInterfaceStyle = baseSettings.userInterfaceStyle;''',
        'request host orientation outside guest update transaction')
    return s


def apply(root):
    file=root/SOURCE
    if not file.is_file() or file.is_symlink():raise ValueError('missing pinned fullscreen source')
    old=file.read_text(encoding='utf-8')
    new=decorated(old)
    if decorated(new)!=new:raise ValueError('V139 landscape non-idempotent')
    if new!=old:file.write_text(new,encoding='utf-8')
    print('[PASS] V139 fullscreen media keeps atomic guest viewport and UIKit-owned host rotation')

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: patch_v139_landscape_video_viewport.py <LiveContainer root>')
    apply(Path(sys.argv[1]))
