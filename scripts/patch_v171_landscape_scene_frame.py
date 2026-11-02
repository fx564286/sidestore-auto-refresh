#!/usr/bin/env python3
"""V171: update a maximized guest's native scene frame ONLY in landscape.

The upstream scene settings callback unconditionally swaps width/height for a
landscape scene, even after UIKit has already produced a wide window. V170's
outer-view resize cannot correct the transposed frame inside the guest scene.
Keep the portrait path and intentional non-maximized windows byte-identical.
"""
from pathlib import Path
import sys
FILE=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK="SCARLET_V171_LANDSCAPE_SCENE_FRAME"
OLD="""        if(UIInterfaceOrientationIsLandscape(baseSettings.interfaceOrientation)) {
            settings.frame = CGRectMake(0, 0, newFrame.size.height, newFrame.size.width);
        } else {
            settings.frame = CGRectMake(0, 0, newFrame.size.width, newFrame.size.height);
        }"""
NEW="""        if(UIInterfaceOrientationIsLandscape(baseSettings.interfaceOrientation)) {
            // SCARLET_V171_LANDSCAPE_SCENE_FRAME: UIKit's fully-rotated
            // maximized host is already wide. Swapping its frame again gives
            // the guest a narrow, portrait-shaped scene centered in landscape.
            // Preserve the previous branch during rotation and for intentional
            // windowed layouts. Never touch the original portrait branch.
            UIWindow *hostWindow = self.view.window;
            BOOL hostCommittedLandscape =
                self.isMaximized && hostWindow &&
                UIInterfaceOrientationIsLandscape(hostWindow.windowScene.interfaceOrientation) &&
                CGRectGetWidth(hostWindow.bounds) > CGRectGetHeight(hostWindow.bounds) + 1.0 &&
                newFrame.size.width > newFrame.size.height + 1.0;
            if (hostCommittedLandscape) {
                settings.frame = CGRectMake(0, 0, newFrame.size.width, newFrame.size.height);
                NSLog(@"[SCARLET_V171_LANDSCAPE] stage=native_scene_frame dimensions=%.0fx%.0f",
                      newFrame.size.width, newFrame.size.height);
            } else {
                settings.frame = CGRectMake(0, 0, newFrame.size.height, newFrame.size.width);
            }
        } else {
            settings.frame = CGRectMake(0, 0, newFrame.size.width, newFrame.size.height);
        }"""

def patch(s:str)->str:
    if MARK in s:
        if s.count(MARK)!=1 or s.count("hostCommittedLandscape")!=2:raise ValueError("partial V171 landscape patch")
        return s
    if "SCARLET_V170_LANDSCAPE_ONLY" not in s:raise ValueError("V170 prerequisite missing")
    if s.count(OLD)!=1:raise ValueError(f"expected one native scene orientation block, found {s.count(OLD)}")
    return s.replace(OLD,NEW,1)

def main(root:Path):
    p=root/FILE
    if not p.is_file() or p.is_symlink():raise ValueError("pinned LiveContainer missing")
    source=p.read_text(encoding="utf-8")
    result=patch(source)
    if patch(result)!=result:raise ValueError("V171 non-idempotent")
    if result!=source:p.write_text(result,encoding="utf-8")
    print("[PASS] V171 landscape-only native guest scene frame; portrait branch unchanged")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v171_landscape_scene_frame.py <LiveContainer>")
    main(Path(sys.argv[1]))
