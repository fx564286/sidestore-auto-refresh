#!/usr/bin/env python3
"""V104: non-destructive retained guest activation order + privacy-safe diagnostics.

The reused virtual guest must be attached and arranged in its real UIWindow
BEFORE sending its remote UIKit scene foreground activation. Existing scene,
PID, container bookmarks, keychain, chat databases and authentication remain
untouched. All diagnostics are booleans/counters without messages or IDs.
"""
from pathlib import Path
import sys

DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
APP = Path("MultitaskSupport/AppSceneViewController.m")
MARK_DOCK = "SCARLET_V104_GUEST_PRESENT_BEFORE_FOREGROUND"
MARK_APP = "SCARLET_V104_SCENE_PROVENANCE"

def replace_one(source, before, after, name):
    count = source.count(before)
    if count != 1:
        raise ValueError(f"V104 {name}: expected one source anchor, found {count}")
    return source.replace(before, after, 1)

def patch_dock(source):
    if MARK_DOCK in source:
        if source.count(MARK_DOCK) != 1 or "controller?.lcResumeMinimizedGuest()" not in source:
            raise ValueError("V104 incomplete guest resume")
        return source
    for marker in ("SCARLET_V103_IMMEDIATE_GUEST_SWITCH",
                   "SCARLET_V97_RETAINED_GUEST_HOST_REBIND",
                   "NRG_V27_GUEST_GEOMETRY"):
        if marker not in source:
            raise ValueError("V104 requires previous retained guest code: " + marker)
    original = '''        controller?.lcResumeMinimizedGuest()
        bringViewToFront(view, in: window)
        // Preserve windowed/maximized frame and the user's chosen scale.'''
    amended = '''        // SCARLET_V104_GUEST_PRESENT_BEFORE_FOREGROUND: remote content
        // must have its retained UIKit view visible and frontmost before
        // posting the foreground scene transition. Otherwise a UIKit guest
        // can receive didBecomeActive while still hidden/behind another view
        // and defer the first data-driven list render (e.g. conversations).
        // No guest recreation, container selection or app-specific hooks.
        bringViewToFront(view, in: window)
        view.layoutIfNeeded()
        controller?.appSceneVC.view.layoutIfNeeded()
        controller?.lcResumeMinimizedGuest()
        NSLog("[SCARLET_V104_GUEST] stage=reactivate visible=%d host_window=%d content_window=%d retained=1",
              view.isHidden ? 0 : 1, view.window != nil ? 1 : 0,
              controller?.appSceneVC.contentView?.window != nil ? 1 : 0)
        // Preserve windowed/maximized frame and the user's chosen scale.'''
    return replace_one(source, original, amended, "guest present before activate")

def patch_app(source):
    if MARK_APP in source:
        if source.count(MARK_APP) != 1 or "[SCARLET_V104_CONTAINER]" not in source:
            raise ValueError("V104 incomplete scene source")
        return source
    if "NRG_V28_GUEST_LIFECYCLE" not in source or "LC_GUEST_RETURN_V3" not in source:
        raise ValueError("V104 requires existing V28 scene lifecycle and guest bookmarks")
    start = '''- (void)lcSetGuestSceneForeground:(BOOL)foreground {
    if (!self.isAppRunning || !self.presenter) return;'''
    result = '''- (void)lcSetGuestSceneForeground:(BOOL)foreground {
    // SCARLET_V104_SCENE_PROVENANCE: scene state only. No messages,
    // credentials, bundle/container identifiers or security tokens.
    BOOL running = self.isAppRunning;
    BOOL presenterAvailable = self.presenter != nil;
    BOOL contentAttached = self.contentView.window != nil;
    NSLog(@"[SCARLET_V104_SCENE] requested_foreground=%d running=%d presenter_ready=%d content_attached=%d hosting_api=%d content_bounds_valid=%d",
          foreground ? 1 : 0, running ? 1 : 0,
          presenterAvailable ? 1 : 0, contentAttached ? 1 : 0,
          self.usesHostingControllerAPI ? 1 : 0,
          CGRectIsEmpty(self.contentView.bounds) ? 0 : 1);
    if (!running || !presenterAvailable) return;'''
    source = replace_one(source, start, result, "scene lifecycle provenance")
    old = '''            if(containerBookmark) {
                [bookmarks addObject:containerBookmark];
            }'''
    new = '''            // V104: explain blank guest data without exposing private paths
            // or reading any database, keychain item, or conversation.
            NSLog(@"[SCARLET_V104_CONTAINER] private_container_exists=%d bookmark_created=%d shared_app=0",
                  [[NSFileManager defaultManager] fileExistsAtPath:dataURL.path] ? 1 : 0,
                  containerBookmark != nil ? 1 : 0);
            if(containerBookmark) {
                [bookmarks addObject:containerBookmark];
            }'''
    source = replace_one(source, old, new, "non-secret container bookmark health")
    return source

def apply(root):
    files = (root / DOCK, root / APP)
    if any(not f.is_file() or f.is_symlink() for f in files):
        raise ValueError("Expected pinned generated host sources")
    old = [p.read_text(encoding="utf-8") for p in files]
    funcs = (patch_dock, patch_app)
    new = [fn(s) for fn, s in zip(funcs, old)]
    if any(fn(s) != s for fn, s in zip(funcs, new)):
        raise ValueError("V104 not idempotent")
    for p, was, now in zip(files, old, new):
        if was != now:
            p.write_text(now, encoding="utf-8")
    print("[PASS] V104 guest presented before remote activation; safe scene/container diagnostics")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v104_guest_scene_reactivation.py <LiveContainer>")
    apply(Path(sys.argv[1]))
