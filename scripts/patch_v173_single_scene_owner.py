#!/usr/bin/env python3
"""V173: a single UIKit geometry writer for the maximized guest scene.

V170's one-shot landscape writer, V171's forced orientation and V172's second
writer race the existing V55/V151 native guest scene path. Remove those
competing writers, not the portrait safe-area policy or guest data. V55/V151
is the only surviving bridge from a committed host UIWindow to guest scene.
"""
from pathlib import Path
import sys
from patch_v172_scene_restore import NEW as V172_OVERRIDDEN_ORIENTATION

FILE=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK="SCARLET_V173_SINGLE_SCENE_GEOMETRY_OWNER"
START="- (void)nrgV169ScheduleGeometry {"
END="\n- (void)viewSafeAreaInsetsDidChange {"
ORIENTATION='''        settings.interfaceOrientation = baseSettings.interfaceOrientation;
        settings.deviceOrientation = baseSettings.deviceOrientation;
        // SCARLET_V171_LANDSCAPE_SCENE_FRAME: retired after ownership audit.
        // SCARLET_V172_RESTORE_PORTRAIT: retired with forced orientation.
        // The guest scene retains its explicitly requested orientation; the
        // single native V55/V151 geometry bridge uses UIWindow for frame size.
        // Never force a portrait-only app to landscape just to stretch media.'''
NEW_HOOK='''// SCARLET_V173_SINGLE_SCENE_GEOMETRY_OWNER: V55/V151 is the sole
// committed frame writer. The V170 one-shot and V172 promotion/restore
// writers have been removed instead of layering additional overrides.
- (void)nrgV169ScheduleGeometry {
    if (!self.isMaximized || !self.appSceneVC.isAppRunning || self.view.hidden) return;
    UIWindow *window = self.view.window;
    if (!window || !self.view.superview || ![self nrgV136GeometryStable:window]) return;
    CGRect measured = [self.view.superview convertRect:self.view.frame toView:window];
    CGSize size = window.bounds.size;
    UIEdgeInsets insets = window.safeAreaInsets;
    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    CGSize guest = self.appSceneVC.view.bounds.size;
    CGSize expected = self.view.bounds.size;
    BOOL staleGuest = fabs(guest.width - expected.width) > 1.0 ||
                      fabs(guest.height - expected.height) > 1.0;
    BOOL physicalChanged = !CGRectEqualToRect(measured, self.nrgV169LastMeasuredViewport) ||
                           !CGSizeEqualToSize(size, self.nrgV169LastMeasuredSize) ||
                           !UIEdgeInsetsEqualToEdgeInsets(insets, self.nrgV169LastMeasuredInsets) ||
                           orientation != self.nrgV169LastMeasuredOrientation;
    if (!staleGuest && !physicalChanged) return;
    self.nrgV169LastMeasuredViewport = measured;
    self.nrgV169LastMeasuredSize = size;
    self.nrgV169LastMeasuredInsets = insets;
    self.nrgV169LastMeasuredOrientation = orientation;
    if (self.nrgV169GeometryQueued) return;
    self.nrgV169GeometryQueued = YES;
    __weak typeof(self) weakSelf = self;
    dispatch_async(dispatch_get_main_queue(), ^{
        __strong typeof(weakSelf) owner = weakSelf;
        if (!owner) return;
        owner.nrgV169GeometryQueued = NO;
        UIWindow *settled = owner.view.window;
        if (!owner.isMaximized || !settled || !owner.appSceneVC.isAppRunning ||
            owner.view.hidden || ![owner nrgV136GeometryStable:settled]) return;
        // V55 has its own per-orientation cache. When safe-area or the guest
        // surface changed without size/orientation changes, invalidate that
        // cache and let V55 do ONE complete frame+settings transaction.
        owner.nrgV55LastHostOrientation = UIInterfaceOrientationUnknown;
        [owner nrgV55ReconcileRotationGeometry];
        NSLog(@"[SCARLET_V173_GEOMETRY] stage=single_owner orientation=%ld window=%.0fx%.0f guest=%.0fx%.0f stale=%d",
              (long)settled.windowScene.interfaceOrientation,
              settled.bounds.size.width, settled.bounds.size.height,
              owner.appSceneVC.view.bounds.size.width, owner.appSceneVC.view.bounds.size.height,
              staleGuest ? 1 : 0);
    });
}
'''
def patch(source:str)->str:
    if MARK in source:
        if source.count(MARK)!=1 or "stage=single_owner" not in source:
            raise ValueError("V173 partially applied")
        return source
    for required in ("SCARLET_V169_EVENT_DRIVEN_VIEWPORT",
                     "SCARLET_V170_LANDSCAPE_ONLY",
                     "SCARLET_V171_LANDSCAPE_SCENE_FRAME",
                     "SCARLET_V172_RESTORE_PORTRAIT",
                     "SCARLET_V151_UNIFIED_GUEST_GEOMETRY"):
        if required not in source:
            raise ValueError("V173 missing exact predecessor "+required)
    if source.count(V172_OVERRIDDEN_ORIENTATION)!=1:
        raise ValueError("V173 cannot find exact V172 guest orientation override")
    source=source.replace(V172_OVERRIDDEN_ORIENTATION,ORIENTATION,1)
    if source.count(START)!=1 or source.count(END)!=1:
        raise ValueError("V173 source has ambiguous scene reconciler")
    a=source.index(START)
    b=source.index(END,a)
    current=source[a:b]
    for token in ("nrgV170LandscapeRepairAttempted","nrgV172LandscapeWasForced",
                  "[owner.appSceneVC updateFrameWithSettingsBlock:",
                  "[owner nrgV55ReconcileRotationGeometry]"):
        if token not in current: raise ValueError("V173 missing legacy owner "+token)
    source=source[:a]+NEW_HOOK+source[b:]
    if source.count(MARK)!=1 or source.count("[owner nrgV55ReconcileRotationGeometry];")!=1:
        raise ValueError("V173 not single geometry writer")
    return source

def main(root:Path):
    p=root/FILE
    if not p.is_file() or p.is_symlink(): raise ValueError("missing audited source")
    old=p.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new: raise ValueError("V173 not idempotent")
    if old!=new: p.write_text(new,encoding="utf-8")
    print("[PASS] V173 one scene owner; no portrait policy or data modifications")

if __name__=="__main__":
    if len(sys.argv)!=2: raise SystemExit("usage: patch_v173_single_scene_owner.py <LiveContainer>")
    main(Path(sys.argv[1]))
