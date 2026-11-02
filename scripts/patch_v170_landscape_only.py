#!/usr/bin/env python3
"""V170: strictly landscape-only guest viewport recovery.

Applied after V169. Portrait frames, portrait safe area calculations,
portrait orientation updates, and all signing/pairing assets are immutable.
A bounded one-shot landscape scene resize handles a retained portrait-sized
guest after UIKit already committed the landscape window.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V170_LANDSCAPE_ONLY"
PATH = Path("MultitaskSupport/DecoratedAppSceneViewController.m")


def once(s: str, old: str, new: str, label: str) -> str:
    n = s.count(old)
    if n != 1:
        raise ValueError(f"V170 landscape {label}: expected one anchor, found {n}")
    return s.replace(old, new, 1)


def patch(s: str) -> str:
    if MARK in s:
        if s.count(MARK) != 1 or "nrgV170LandscapeRepairAttempted" not in s:
            raise ValueError("V170 partial landscape patch")
        return s
    for marker in (
        "SCARLET_V169_EVENT_DRIVEN_VIEWPORT",
        "SCARLET_V151_UNIFIED_GUEST_GEOMETRY",
        "SCARLET_V136_ROTATION_ATOMIC",
    ):
        if marker not in s:
            raise ValueError("missing previous source " + marker)

    s = once(s,
        "@property(nonatomic) BOOL nrgV169GeometryQueued;",
        "@property(nonatomic) BOOL nrgV169GeometryQueued;\n"
        "// " + MARK + ": bounded recovery without altering portrait behavior.\n"
        "@property(nonatomic) BOOL nrgV170LandscapeRepairAttempted;",
        "landscape-only state")

    s = once(s,
        """    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    if (CGRectEqualToRect(measured, self.nrgV169LastMeasuredViewport) &&""",
        """    UIInterfaceOrientation orientation = window.windowScene.interfaceOrientation;
    // The portrait pipeline is left completely unchanged. A landscape guest
    // may become portrait-sized after media fullscreen even when the physical
    // UIWindow frame has not changed and V169's geometry cache matches.
    BOOL nrgV170LandscapeNeedsRepair = NO;
    if (UIInterfaceOrientationIsLandscape(orientation) &&
        size.width > size.height + 1.0) {
        // Rearm only when ENTERING landscape or its committed dimensions change.
        // No portrait layout/state path is modified.
        if (self.nrgV169LastMeasuredOrientation != orientation ||
            !CGSizeEqualToSize(size, self.nrgV169LastMeasuredSize)) {
            self.nrgV170LandscapeRepairAttempted = NO;
        }
        CGFloat usableWidth = size.width - insets.left - insets.right;
        CGFloat usableHeight = size.height - insets.top - insets.bottom;
        CGSize guestSize = self.appSceneVC.view.bounds.size;
        CGSize viewportSize = self.view.bounds.size;
        BOOL narrowHost = CGRectGetWidth(measured) + 1.0 < usableWidth ||
                          CGRectGetHeight(measured) + 1.0 < usableHeight;
        BOOL narrowGuest = fabs(guestSize.width - viewportSize.width) > 1.0 ||
                           fabs(guestSize.height - viewportSize.height) > 1.0;
        nrgV170LandscapeNeedsRepair = narrowHost || narrowGuest;
        if (!nrgV170LandscapeNeedsRepair) {
            self.nrgV170LandscapeRepairAttempted = NO;
        }
    }
    if (CGRectEqualToRect(measured, self.nrgV169LastMeasuredViewport) &&""",
        "landscape-only stale detection")

    s = once(s,
        """        orientation == self.nrgV169LastMeasuredOrientation) return;""",
        """        orientation == self.nrgV169LastMeasuredOrientation &&
        (!nrgV170LandscapeNeedsRepair || self.nrgV170LandscapeRepairAttempted)) return;""",
        "bypass geometry cache only when stale landscape")

    s = once(s,
        """        owner.nrgV169GeometryQueued = NO;
        [owner nrgV55ReconcileRotationGeometry];""",
        """        owner.nrgV169GeometryQueued = NO;
        // Never enter this branch in portrait. Repair at most once per stale
        // interval; the next correct landscape layout rearms the detector.
        UIWindow *currentWindow = owner.view.window;
        if (nrgV170LandscapeNeedsRepair &&
            !owner.nrgV170LandscapeRepairAttempted &&
            currentWindow &&
            [owner nrgV136GeometryStable:currentWindow] &&
            UIInterfaceOrientationIsLandscape(currentWindow.windowScene.interfaceOrientation) &&
            currentWindow.bounds.size.width > currentWindow.bounds.size.height + 1.0 &&
            owner.isMaximized && owner.appSceneVC.isAppRunning) {
            owner.nrgV170LandscapeRepairAttempted = YES;
            [owner.appSceneVC updateFrameWithSettingsBlock:^(UIMutableApplicationSceneSettings *settings) {
                if (owner.isMaximized &&
                    UIInterfaceOrientationIsLandscape(owner.view.window.windowScene.interfaceOrientation)) {
                    [owner updateMaximizedFrameWithSettings:settings];
                }
            }];
            NSLog(@"[SCARLET_V170_LANDSCAPE] stage=repair host=%.0fx%.0f",
                  currentWindow.bounds.size.width, currentWindow.bounds.size.height);
        }
        [owner nrgV55ReconcileRotationGeometry];""",
        "one-shot landscape repair")

    return s


def apply(root: Path) -> None:
    target = root / PATH
    if not target.is_file() or target.is_symlink():
        raise ValueError("expected pinned LiveContainer source missing")
    original = target.read_text(encoding="utf-8")
    updated = patch(original)
    if patch(updated) != updated:
        raise ValueError("V170 patch is not idempotent")
    if updated != original:
        target.write_text(updated, encoding="utf-8")
    print("[PASS] V170 landscape-only viewport patch")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v170_landscape_only.py <LiveContainer>")
    apply(Path(sys.argv[1]))
