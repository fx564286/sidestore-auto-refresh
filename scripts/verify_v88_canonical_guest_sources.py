#!/usr/bin/env python3
"""V88 fail-closed audit of FINAL generated LiveContainer UI sources.

Do not ship sources that retain removed Island/overlay functionality, duplicate
recent-guest routes, or the V87 after-the-fact overlay patch.
This verifier is read-only. It never replaces an unsafe source with a stub.
"""
from pathlib import Path
import json
import re
import sys

DOCK = Path("MultitaskSupport/MultitaskDockView.swift")
SCENE = Path("MultitaskSupport/AppSceneViewController.m")
WINDOW = Path("MultitaskSupport/DecoratedAppSceneViewController.m")
SHELL = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
MODEL = Path("LiveContainerSwiftUI/Models/LCAppModel.swift")
PLIST = Path("LiveContainer/Info.plist")

# No universal removal of old identifiers: some V192/V58 guest lifecycle
# fixes are live and are essential for the user's existing apps.
BANNED = {
    DOCK: [
        "import ActivityKit", "NRGGuestActivityAttributes",
        "nrgV56RelayoutIsland", "nrgV56ShowGuestControls",
        "nrgV58RefreshNativeIsland", "nrgV61NoteGuestUse",
        "nrgV56IslandExpanded", "nrgV56IslandHidden",
    ],
    SHELL: ["nrgV192RefreshIslandIfReady", "NRGGuestActivityAttributes"],
    MODEL: ["nrgV58RefreshNativeIsland", "NRG_V63_NOTIFY_GUEST_LAUNCH"],
}
REQUIRED = {
    DOCK: {
        "func nrgV72PresentGuestSwitcher": 1,
        "SCARLET_V87_NATIVE_RUNNING_GUESTS": 1,
        "MultitaskWindowManager.appDict.values": 1,
        "SCARLET_V89_IOS161_AVAILABILITY": 1,
        "if #available(iOS 16.1, *)": 2,
        "MultitaskWindowManager.openExistingAppWindow(dataUUID: guest.folder)": 1,
    },
    SCENE: {
        "- (void)lcV76ShowInstalledGuestSwitcher": 1,
        "SCARLET_V87_HOST_GUEST_PICKER": 1,
        "owner.rootViewController": 1,
        "nrgV72PresentGuestSwitcherFrom:presenter": 1,
        "[self.button addGestureRecognizer:v76Hold]": 1,
    },
    WINDOW: {
        "- (void)nrgV72WindowOverflowLongPress:": 1,
        "nrgV72PresentGuestSwitcherFrom:self": 1,
    },
}
DEAD_OVERLAY = Path("scripts/patch_v87_guest_button_switcher.py")


def check_file(root: Path, relative: Path, content: str, problems: list[str]):
    for token, wanted in REQUIRED.get(relative, {}).items():
        found = content.count(token)
        if found != wanted:
            problems.append(f"{relative}: required final UI token {token!r} count={found}; wanted={wanted}")
    for token in BANNED.get(relative, []):
        if token in content:
            problems.append(f"{relative}: retired code still exists: {token}")
    if relative == SCENE:
        for forbidden in ('UIApplicationStateActive', 'ignored=presenter_has_no_window'):
            if forbidden in content:
                problems.append(f"{relative}: stale V76 hold guard {forbidden}")
    if relative == DOCK:
        if "DataManager.shared.model.apps" not in content:
            problems.append("Host installed-app registry missing from guest picker")
        if 'lastLaunched' not in content or "48 * 60 * 60" not in content:
            problems.append("Recent guest selection policy lost")


def audit(root: Path, source_repo: Path | None = None) -> dict:
    problems: list[str] = []
    paths = tuple(dict.fromkeys([*REQUIRED, *BANNED]))
    counts: dict[str, int] = {}
    for relative in paths:
        path = root / relative
        if not path.is_file():
            problems.append(f"Generated source missing: {relative}")
            continue
        content = path.read_text(encoding="utf-8")
        counts[str(relative)] = len(content.encode("utf-8"))
        check_file(root, relative, content, problems)
    if source_repo is not None and (source_repo / DEAD_OVERLAY).exists():
        problems.append("V87 obsolete overlay patch still exists in the build source; remove, do not disable")
    info = root / PLIST
    if not info.exists():
        problems.append("Host Info.plist missing")
    else:
        import plistlib
        data = plistlib.loads(info.read_bytes())
        if "NSSupportsLiveActivities" in data:
            problems.append("Retired Live Activity setting survived on the host")
        if not any("scarletcrystal251" in v.get("CFBundleURLSchemes", [])
                   for v in data.get("CFBundleURLTypes", [])):
            problems.append("Host guest deep link missing")
    return {
        "status": "PASS" if not problems else "FAIL",
        "scope": "generated LiveContainer host UI (not entire native binary)",
        "files": counts,
        "errors": problems,
    }


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: verify_v88_canonical_guest_sources.py <final-source> [builder]")
    result = audit(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) == 3 else None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 2)
