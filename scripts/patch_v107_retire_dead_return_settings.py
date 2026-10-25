#!/usr/bin/env python3
"""Delete obsolete guest Return settings following the V105 SOURCE migration.

V105 deletes the Return UIView/Direct presenter. Their five SwiftUI settings
still rendered and wrote unused UserDefaults keys. Remove the dead controls
and their exclusive color conversion function; do NOT reset any stored values,
change live guest controls, alter signing, or affect independent JIT settings.
"""
from pathlib import Path
import sys

SETTINGS = Path("LiveContainerSwiftUI/Views/Settings/LCSettingsView.swift")
MARK = "SCARLET_V107_RETIRE_DEAD_RETURN_SETTINGS"
OLD_KEYS = (
    'LCHideReturnControl', 'LCGuestReturnStartsCollapsed',
    'LCGuestReturnCustomColors', 'LCGuestReturnTintRGB',
    'LCGuestReturnBackgroundRGB',
)
OLD_ROWS = ('Show Return Button', 'Use Custom Colors', 'Button Background',
            'Start Collapsed shows an edge tab')


def between(src: str, start: str, end: str, replacement: str, label: str) -> str:
    if src.count(start) != 1 or src.count(end) != 1 or src.index(start) >= src.index(end):
        raise ValueError(f"V107 unexpected {label} source anchors: {src.count(start)} / {src.count(end)}")
    return src[:src.index(start)] + replacement + src[src.index(end):]


def patch(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1:
            raise ValueError("V107 settings marker not unique")
        if any(key in source for key in OLD_KEYS + OLD_ROWS + ('returnColorBinding(',)):
            raise ValueError("V107 settings partially migrated; old Return UI survives")
        return source
    if 'V3AccountSettings()' not in source or 'LCJITLessDiagnoseView()' not in source:
        raise ValueError("V107 missing required live account/JIT settings; fail closed")
    if any(source.count(f'@AppStorage("{key}"') != 1 for key in OLD_KEYS):
        raise ValueError("V107 obsolete Return preference declarations drifted")
    source = between(
        source,
        '    @AppStorage("LCHideReturnControl"',
        '    @State var errorShow = false',
        f'    // {MARK}: no settings for deleted Return controls.\n',
        "obsolete Return preferences",
    )
    source = between(
        source,
        '    private func returnColorBinding(_ rgb: Binding<Int>) -> Binding<Color> {',
        '    var body: some View {',
        '',
        "obsolete Return-only ColorPicker binding",
    )
    source = between(
        source,
        '                Section {\n                    Toggle("Show Return Button",',
        '                Section {\n                    NavigationLink { LCEmbeddedSideStoreRefreshView() }',
        '',
        "obsolete Return settings Form section",
    )
    if any(key in source for key in OLD_KEYS + OLD_ROWS + ('returnColorBinding(',)):
        raise ValueError("V107 dead Return preferences still referenced")
    for required in ('V3AccountSettings()', 'LCJITLessDiagnoseView()',
                     'NavigationLink { LCEmbeddedSideStoreRefreshView() }'):
        if required not in source:
            raise ValueError("V107 active host settings lost: " + required)
    return source


def apply(root: Path) -> None:
    target = root / SETTINGS
    if not target.is_file() or target.is_symlink():
        raise ValueError("V107 pinned generated LCSettingsView missing")
    original = target.read_text(encoding="utf-8")
    updated = patch(original)
    assert patch(updated) == updated
    if updated != original:
        target.write_text(updated, encoding="utf-8")
    print("[PASS] V107 removed dead Return settings source; active Settings and data preserved")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v107_retire_dead_return_settings.py <generated host source>")
    apply(Path(sys.argv[1]))
