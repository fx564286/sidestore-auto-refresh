#!/usr/bin/env python3
"""V174: committed UIKit viewport owns rendered content; bounded scene repairs.

Audit references: V173 geometry event, pinned AppSceneViewController's
iOS 27 contentView.frame assignment and Native V28 foreground lifecycle.
Do not recreate guests or alter SideStore signing, pairing, permissions,
audio session, data, or windowed guest layout.
"""
from pathlib import Path
import sys
HOST=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
GUEST=Path("MultitaskSupport/AppSceneViewController.m")
MARK_HOST="SCARLET_V174_BOUNDED_GEOMETRY"
MARK_GUEST="SCARLET_V174_RENDER_SURFACE"
OLD_STATE='''@property(nonatomic) BOOL nrgV169GeometryQueued;'''
NEW_STATE='''@property(nonatomic) BOOL nrgV169GeometryQueued;
// SCARLET_V174_BOUNDED_GEOMETRY: one repair per settled geometry epoch,
// avoiding an endless settings/layout feedback loop during media playback.
@property(nonatomic) BOOL nrgV174RepairAttempted;'''
OLD_GATE='''    if (!staleGuest && !physicalChanged) return;
    self.nrgV169LastMeasuredViewport = measured;'''
NEW_GATE='''    if (!staleGuest && !physicalChanged) {
        self.nrgV174RepairAttempted = NO;
        return;
    }
    if (physicalChanged) self.nrgV174RepairAttempted = NO;
    if (staleGuest && !physicalChanged && self.nrgV174RepairAttempted) return;
    self.nrgV169LastMeasuredViewport = measured;'''
OLD_COMMIT='''        // V55 has its own per-orientation cache. When safe-area or the guest
        // surface changed without size/orientation changes, invalidate that
        // cache and let V55 do ONE complete frame+settings transaction.
        owner.nrgV55LastHostOrientation = UIInterfaceOrientationUnknown;
        [owner nrgV55ReconcileRotationGeometry];'''
NEW_COMMIT='''        // V55/V151 performs the ONLY guest settings transaction.
        // One bounded stale-surface repair is allowed per physical epoch.
        owner.nrgV174RepairAttempted = YES;
        owner.nrgV55LastHostOrientation = UIInterfaceOrientationUnknown;
        [owner nrgV55ReconcileRotationGeometry];'''
OLD_RENDER='''    if (self.contentView) {
        BOOL isiOS26 = NO;'''
NEW_RENDER='''    // SCARLET_V174_RENDER_SURFACE: iOS 27 remote scene hosting can
    // retain a portrait-sized scene.frame even when the real parent UIView
    // has settled in landscape. The host's actual on-screen child bounds
    // determine the rendered surface; tempSettings.frame is only metadata.
    // Preserve the V151 portrait safe-area *origin* in the parent view.
    if (@available(iOS 27.0, *)) {
        if (self.usesHostingControllerAPI &&
            [self.delegate isKindOfClass:DecoratedAppSceneViewController.class]) {
            DecoratedAppSceneViewController *decorated =
                (DecoratedAppSceneViewController *)self.delegate;
            UIWindow *hostWindow = decorated.view.window;
            UIInterfaceOrientation committed = hostWindow.windowScene.interfaceOrientation;
            CGSize physical = hostWindow.bounds.size;
            BOOL committedDimensions =
                (UIInterfaceOrientationIsPortrait(committed) &&
                 physical.height >= physical.width - 1.0) ||
                (UIInterfaceOrientationIsLandscape(committed) &&
                 physical.width >= physical.height - 1.0);
            if (decorated.isMaximized && hostWindow && committedDimensions &&
                self.view.window == hostWindow && !CGRectIsEmpty(self.view.bounds)) {
                CGRect renderedBounds = self.view.bounds;
                renderedBounds.origin = CGPointZero;
                if (fabs(frame.size.width - renderedBounds.size.width) > 1.0 ||
                    fabs(frame.size.height - renderedBounds.size.height) > 1.0) {
                    NSLog(@"[SCARLET_V174_MEDIA_SURFACE] stage=align_rendered_view host=%ld scene=%.0fx%.0f rendered=%.0fx%.0f",
                          (long)committed, frame.size.width, frame.size.height,
                          renderedBounds.size.width, renderedBounds.size.height);
                }
                frame = renderedBounds;
            }
        }
    }
    if (self.contentView) {
        BOOL isiOS26 = NO;'''
def once(s,a,b,name):
    if s.count(a)!=1:raise ValueError(f"V174 {name}: expected 1 anchor, got {s.count(a)}")
    return s.replace(a,b,1)
def decorated(s):
    if MARK_HOST in s:
        if s.count(MARK_HOST)!=1 or "nrgV174RepairAttempted = YES;" not in s:
            raise ValueError("V174 host partial")
        return s
    for req in ("SCARLET_V173_SINGLE_SCENE_GEOMETRY_OWNER",
                "SCARLET_V151_ORIENTATION_PARITY","SCARLET_V169_EVENT_DRIVEN_VIEWPORT"):
        if req not in s:raise ValueError("V174 missing prerequisite: "+req)
    s=once(s,OLD_STATE,NEW_STATE,"state")
    s=once(s,OLD_GATE,NEW_GATE,"stable geometry gate")
    s=once(s,OLD_COMMIT,NEW_COMMIT,"one scene commit")
    return s
def guest(s):
    if MARK_GUEST in s:
        if s.count(MARK_GUEST)!=1 or "stage=align_rendered_view" not in s:
            raise ValueError("V174 guest partial")
        return s
    for req in ("SCARLET_V104_SCENE_PROVENANCE", "NRG_V28_GUEST_LIFECYCLE"):
        if req not in s:raise ValueError("V174 missing foreground source: "+req)
    if "self.hostingController.sceneViewController.view" not in s:
        raise ValueError("V174 missing pinned remote host rendering API")
    return once(s,OLD_RENDER,NEW_RENDER,"iOS27 renderer")
def apply(root):
    outputs=[]
    for rel,transform in ((HOST,decorated),(GUEST,guest)):
        p=root/rel
        if not p.is_file() or p.is_symlink():raise ValueError("V174 pinned source absent")
        old=p.read_text(encoding="utf-8")
        new=transform(old)
        if transform(new)!=new:raise ValueError("V174 not idempotent")
        outputs.append((p,old,new))
    for p,old,new in outputs:
        if new!=old:p.write_text(new,encoding="utf-8")
    print("[PASS] V174 bounded UIKit scene reconciler + iOS27 native media surface")
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v174_guest_render.py <LiveContainer>")
    apply(Path(sys.argv[1]))
