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
    requirements = {
        NATIVE: ("SCARLET_V105_LEGACY_RETURN_SOURCE_DELETED",),
        VIRTUAL: ("SCARLET_V103_VIRTUAL_ONLY_CONTROL", "scarlet.v103.virtual.guest.control"),
        DOCK: ("SCARLET_V103_IMMEDIATE_GUEST_SWITCH", "defer { dismissSelection() }",
               "SCARLET_V108_NO_BLUE_COLLAPSED_DOCK",
               "if dockManager.v3DockPresentationState.isReady &&",
               "!dockManager.isDockHidden && !dockManager.apps.isEmpty",
               "ForEach(dockManager.apps) { app in",
               "SCARLET_V107_LIVE_WINDOW_ACTIONS_ONLY",
               "guard controller is DecoratedAppSceneViewController",
               '("최소화", "minimizeWindow")',
               '("최대화 / 복원", "maximizeWindow")',
               '("창 닫기", "closeWindow")'),
        DIRECT: ("SCARLET_V105_DIRECT_UNIFIED_MORPH", "SCGuestMorphPresenter",
                 "SCGuestMorphWindow", "scarlet.v105.direct.morph",
                 "root.safeAreaInsets", "portraitUI ? 44 : 28",
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
                     'Image(systemName: "chevron.up")', "hideCollapsedDock",
                     "keyWindow.gestureRecognizers?.removeAll"):
        if obsolete in dock:
            problems.append("V108 blue Dock implementation survived: " + obsolete)
    for stale in ("lcReturnToHost", "lcV102CollapseFloatingButton", "홍수정"):
        if stale in dock:
            problems.append("Retired Dock menu selector/branding survived: " + stale)
    return {"status": "FAIL" if problems else "PASS", "problems": problems,
            "scanned": [str(x) for x in files],
            "owners": ["V102/V103 virtual-host morph", "V105 Direct morph"],
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
