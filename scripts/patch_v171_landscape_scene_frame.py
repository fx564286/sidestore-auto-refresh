#!/usr/bin/env python3
"""V171: reconcile a maximized guest's orientation only after host landscape commits.

V139 already REMOVED the old duplicate settings.frame write. V171 therefore
must NOT patch that retired code. The remaining narrow portrait guest can
persist because the native scene has baseSettings.interfaceOrientation portrait
even while the foreground host UIWindow is committed landscape. This guarded
branch changes only that landscape mismatch; the original portrait assignment
and windowed scene behavior remain untouched.
"""
from pathlib import Path
import sys
FILE=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK="SCARLET_V171_LANDSCAPE_SCENE_FRAME"
OLD="""        settings.interfaceOrientation = baseSettings.interfaceOrientation;
        settings.deviceOrientation = baseSettings.deviceOrientation;"""
NEW="""        settings.interfaceOrientation = baseSettings.interfaceOrientation;
        settings.deviceOrientation = baseSettings.deviceOrientation;
        // SCARLET_V171_LANDSCAPE_SCENE_FRAME: only a real, committed
        // landscape UIWindow may correct a portrait-retained maximized guest.
        // A portrait UIWindow and every intentional windowed guest use the
        // unchanged original scene orientation and safe-area pipeline.
        UIWindow *hostWindow = self.view.window;
        UIInterfaceOrientation hostOrientation = hostWindow.windowScene.interfaceOrientation;
        BOOL hostCommittedLandscape = self.isMaximized &&
            self.appSceneVC.isAppRunning && hostWindow &&
            UIInterfaceOrientationIsLandscape(hostOrientation) &&
            CGRectGetWidth(hostWindow.bounds) > CGRectGetHeight(hostWindow.bounds) + 1.0;
        if (hostCommittedLandscape &&
            UIInterfaceOrientationIsPortrait(settings.interfaceOrientation)) {
            settings.interfaceOrientation = hostOrientation;
            // The public interface and device orientation have opposite
            // left/right naming, as observed by UIKit.
            settings.deviceOrientation =
                hostOrientation == UIInterfaceOrientationLandscapeLeft
                    ? UIDeviceOrientationLandscapeRight : UIDeviceOrientationLandscapeLeft;
            NSLog(@"[SCARLET_V171_LANDSCAPE] stage=guest_orientation_sync host=%ld",
                  (long)hostOrientation);
        }"""

def patch(s:str)->str:
    if MARK in s:
        if s.count(MARK)!=1 or s.count("hostCommittedLandscape")!=2:
            raise ValueError("partial V171 landscape patch")
        return s
    for required in ("SCARLET_V170_LANDSCAPE_ONLY", "SCARLET_V139_VIDEO_LANDSCAPE_GEOMETRY",
                     "SCARLET_V151_UNIFIED_GUEST_GEOMETRY"):
        if required not in s:raise ValueError("V171 prerequisite missing: "+required)
    if s.count(OLD)!=1:raise ValueError(f"expected one native scene orientation assignment, got {s.count(OLD)}")
    return s.replace(OLD,NEW,1)

def main(root:Path):
    p=root/FILE
    if not p.is_file() or p.is_symlink():raise ValueError("pinned LiveContainer missing")
    old=p.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:raise ValueError("V171 patch not idempotent")
    if new!=old:p.write_text(new,encoding="utf-8")
    print("[PASS] V171 committed-landscape native guest orientation; portrait path unchanged")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v171_landscape_scene_frame.py <LiveContainer>")
    main(Path(sys.argv[1]))
