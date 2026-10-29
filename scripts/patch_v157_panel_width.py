#!/usr/bin/env python3
"""V157: enlarge the single existing native panel horizontally without
changing its height, segments, clear-glass optics, animations or outside taps.
Applies AFTER V156. Strict one-anchor, idempotent fail-closed transform.
"""
from pathlib import Path
import sys

DOCK=Path("MultitaskSupport/MultitaskDockView.swift")
OLD="""        let availableWidth = max(260, owner.bounds.width - 48)
        let panelWidth = min(352, availableWidth)"""
NEW="""        // SCARLET_V157_WIDE_PANEL: ~16pt safe breathing room each side.
        // Prior 352pt cap left the window visibly narrower than requested.
        // Preserve iPad max and tiny-window minimum from the legacy picker.
        let availableWidth = max(260, owner.bounds.width - 32)
        let panelWidth = min(390, availableWidth)
        NSLog("[SCARLET_V157_WIDTH] viewport=%.1f panel=%.1f",
              owner.bounds.width, panelWidth)"""
MARK="SCARLET_V157_WIDE_PANEL"

def patch(src: str) -> str:
    if MARK in src:
        if src.count(MARK)!=1 or OLD in src or NEW not in src:
            raise ValueError("V157 partial/multiple wide-panel patch")
        return src
    for prerequisite in ("SCARLET_V156_STABLE_PANEL_HEIGHT",
                         "SCARLET_V156_ROW_OPTICAL_PAD",
                         "SCARLET_V156_OUTSIDE_TOUCH_TRACE",
                         "SCARLET_V155_DOCK_SINGLE_MODE"):
        if prerequisite not in src:
            raise ValueError("V157 missing previous panel invariant "+prerequisite)
    if src.count(OLD)!=1:
        raise ValueError("V157 width anchor moved; manual review required")
    return src.replace(OLD,NEW,1)

def apply(root: Path):
    f=root/DOCK
    if not f.is_file() or f.is_symlink():
        raise ValueError("V157 generated Dock Swift missing")
    old=f.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:
        raise ValueError("V157 not idempotent")
    if old!=new:
        f.write_text(new,encoding="utf-8")
    print("[PASS] V157 width=screen-32pt/max390pt; prior big height and clearGlass unchanged")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v157_panel_width.py <LiveContainer>")
    apply(Path(sys.argv[1]))
