#!/usr/bin/env python3
"""Read-only audit of FINAL generated guest controls. Never changes runtime data."""
from __future__ import annotations
import argparse
from pathlib import Path
import json

NATIVE = Path("MultitaskSupport/AppSceneViewController.m")
VIRTUAL = Path("MultitaskSupport/DecoratedAppSceneViewController.m")
DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
DIRECT = Path("LiveContainer/LCBootstrap.m")
SETTINGS = Path("LiveContainerSwiftUI/Views/Settings/LCSettingsView.swift")
OBSOLETE = (
    "LCReturnControl", "lcReturnControl", "lcReturnToHost",
    "LCDirectReturnPresenter", "LCDirectReturnControl", "LCDirectReturnWindow",
)


def inspect(root: Path) -> dict:
    files = {k: root / k for k in (NATIVE, VIRTUAL, DOCK, DIRECT, SETTINGS)}
    problems = []
    source = {}
    for rel, path in files.items():
        if not path.is_file() or path.is_symlink():
            problems.append(f"Missing or unsafe final generated source: {rel}")
            continue
        source[rel] = path.read_text(encoding="utf-8")
    if len(source) != len(files):
        return {"status": "FAIL", "problems": problems}
    native, virt, dock, direct, settings = (source[k] for k in (NATIVE, VIRTUAL, DOCK, DIRECT, SETTINGS))
    for rel, body in ((NATIVE,native),(DIRECT,direct)):
        for old in OBSOLETE:
            if old in body:
                problems.append(f"{rel}: retired executable guest control still present: {old}")
    # V137 deliberately deletes the old virtual UI button source. The same
    # shared bootstrap presenter owns Direct and LiveProcess after migration.
    unified = "SCARLET_V137_UNIFIED_GUEST_ENTRY" in direct
    requirements = {
        NATIVE: ("SCARLET_V105_LEGACY_RETURN_SOURCE_DELETED",),
        VIRTUAL: (("SCARLET_V137_UNIFIED_GUEST_ENTRY", "SCARLET_V137_TOUCH_SETTLE")
                  if unified else ("SCARLET_V103_VIRTUAL_ONLY_CONTROL", "scarlet.v103.virtual.guest.control")),
        DOCK: ("SCARLET_V103_IMMEDIATE_GUEST_SWITCH", "defer { dismissSelection() }",
               "SCARLET_V111_CANONICAL_GUEST_SWITCH_OWNER",
               "SCARLET_V112_SHARED_GUEST_UI",
               "@objc(SCUnifiedGuestUIBridge)",
               "scarlet.v112.direct.restart",
               "nrgV72PresentGuestSwitcher(from: controller, sourceView: sourceView)",
               "nrgV102NoteFocus(guest.folder)",
               "SCARLET_V107_LIVE_WINDOW_ACTIONS_ONLY",
               "guard controller is DecoratedAppSceneViewController",
               '("최소화", "minimizeWindow")',
               '("최대화 / 복원", "maximizeWindow")',
               '("창 닫기", "closeWindow")'),
        DIRECT: ("SCARLET_V105_DIRECT_UNIFIED_MORPH", "SCGuestMorphPresenter",
                  "SCGuestMorphWindow",
                 "scarlet.v137.shared.guest.control" if unified else "scarlet.v105.direct.morph",
                 "SCARLET_V112_SHARED_GUEST_UI", "SCUnifiedGuestUIBridge",
                 "UIBlurEffectStyleSystemThinMaterial", "presentFrom:sourceView:",
                 "SCGuestMorphPositionV105", "confirmation=accepted"),
        SETTINGS: ("SCARLET_V107_RETIRE_DEAD_RETURN_SETTINGS",
                   "V3AccountSettings()", "LCJITLessDiagnoseView()",
                   "LCEmbeddedSideStoreRefreshView()"),
    }
    for rel, tokens in requirements.items():
        for token in tokens:
            if token not in source[rel]:
                problems.append(f"{rel}: missing required single-owner marker: {token}")
    if "홍수정" in direct:
        problems.append("Direct guest overlay still uses retired app branding")
    for retired in ("UIButton *scrim", "UIView *card", "UILabel *title",
                    "- (void)expand:", "portraitUI ? 44 : 28",
                    'systemImageNamed:@"chevron.up"'):
        if retired in direct:
            problems.append("V112 separate Direct popup survived: " + retired)
    if dock.count("public func nrgV72PresentGuestSwitcher(") != 1:
        problems.append("V112 shared picker count is not one")
    if dock.count("@objc(SCUnifiedGuestUIBridge)") != 1:
        problems.append("V112 ObjC-to-Swift router count is not one")
    for removed in ("LCHideReturnControl", "LCGuestReturnStartsCollapsed",
                    "LCGuestReturnCustomColors", "LCGuestReturnTintRGB",
                    "LCGuestReturnBackgroundRGB", 'Toggle("Show Return Button"',
                    "returnColorBinding("):
        if removed in settings:
            problems.append("Dead guest Return settings still exist: " + removed)
    if direct.count("@interface SCGuestMorphPresenter : NSObject") != 1:
        problems.append("Direct presenter class owner count is not exactly one")
    if direct.count("static SCGuestMorphPresenter *scGuestMorphPresenter;") != 1:
        problems.append("Direct singleton count is not exactly one")
    if "NRGV56IslandBar" in virt or "nrgV72WindowOverflowLongPress:" in virt:
        problems.append("Earlier floating/Island control code remains in final virtual host")
    if "NRGGuestActivityAttributes" in dock:
        problems.append("Removed ActivityKit widget route remains in final Dock")
    for obsolete in ("struct CollapsedDockView: View", "struct CollapseButtonView: View",
                     "CollapsedDockView(isHidden:", "CollapseButtonView()",
                     "struct MultitaskDockSwiftView: View", "struct AppIconView: View",
                     "UIHostingController<AnyView>", "setupEdgeGestureRecognizers()",
                     'Image(systemName: "chevron.up")', "hideCollapsedDock",
                     "keyWindow.gestureRecognizers?.removeAll"):
        if obsolete in dock:
            problems.append("V108 blue Dock implementation survived: " + obsolete)
    for stale in ("lcReturnToHost", "lcV102CollapseFloatingButton", "홍수정"):
        if stale in dock:
            problems.append("Retired Dock menu selector/branding survived: " + stale)
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "scanned": [str(x) for x in files],
            "owners": ["V137 one bootstrap glass control / Direct+LiveProcess" if unified
                       else "V112 common UIKit morph picker; Direct supplies the entry control only"],
            "source_only": True,
            "device_geometry_verified": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("generated_livecontainer_root", type=Path)
    parser.add_argument("--output", type=Path)
    opts = parser.parse_args()
    report = inspect(opts.generated_livecontainer_root)
    if opts.output:
        opts.output.parent.mkdir(parents=True, exist_ok=True)
        opts.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
