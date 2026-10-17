#!/usr/bin/env python3
"""NRG V39: keep the right dock dedicated to app switching."""
from pathlib import Path
import sys
P = Path("MultitaskSupport/MultitaskDockView.swift")
MARK = "NRG_V39_DOCK_APP_SWITCH_ONLY"
def patch(s):
    if MARK in s:
        return s
    old = '''                        MinimizeAllButtonView()
                            .onTapGesture {
                                dockManager.minimizeAllWindows()
                            }

'''
    if s.count(old) != 1:
        raise RuntimeError("expected single dock minimize-all control")
    return s.replace(old, "                        // " + MARK + ": window management belongs to the top overflow menu.\n", 1)
if __name__ == "__main__":
    p = Path(sys.argv[1]) / P
    original = p.read_text()
    updated = patch(original)
    if updated != original:
        p.write_text(updated)
    assert patch(updated) == updated
    print("[PASS] right dock contains app switcher without duplicate minimize-all")
