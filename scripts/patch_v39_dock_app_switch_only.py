#!/usr/bin/env python3
"""NRG V39: keep the right dock dedicated to app switching."""
from pathlib import Path
import sys
P = Path("MultitaskSupport/MultitaskDockView.swift")
MARK = "NRG_V39_DOCK_APP_SWITCH_ONLY"

GLASS_MARK = "NRG_V42_DOCK_GLASS_HOME"
def add_glass_home(s):
    if GLASS_MARK in s:
        return s
    anchor = "                        ForEach(dockManager.apps) { app in"
    if s.count(anchor) != 1:
        raise RuntimeError("Dock app list anchor mismatch")
    home = '''                        // NRG_V42_DOCK_GLASS_HOME: preserve guest sessions when returning to LC.
                        Button(action: { dockManager.minimizeAllWindows() }) {
                            Image(systemName: "house.fill")
                                .font(.system(size: dockManager.adaptiveIconSize * 0.40, weight: .semibold))
                                .foregroundStyle(.primary)
                                .frame(width: dockManager.adaptiveIconSize, height: dockManager.adaptiveIconSize)
                                .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 13))
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Return to LiveContainer")
                        .accessibilityIdentifier("nrgDockReturnHome")

'''
    s = s.replace(anchor, home + anchor, 1)
    old = "if #available(iOS 26.0, *), SharedModel.isLiquidGlassEnabled {"
    if s.count(old) != 1:
        raise RuntimeError("Dock glass anchor mismatch")
    s = s.replace(old, "if #available(iOS 26.0, *) {", 1)
    return s

def patch(s):
    if MARK in s:
        return add_glass_home(s)
    old = '''                        MinimizeAllButtonView()
                            .onTapGesture {
                                dockManager.minimizeAllWindows()
                            }

'''
    if s.count(old) == 1:
        return add_glass_home(s.replace(old, "                        // " + MARK + ": window management belongs to top overflow.\n", 1))
    import re
    pattern = r"(?m)^[ \t]*MinimizeAllButtonView\(\)[ \t]*\n[ \t]*\.onTapGesture[ \t]*\{[ \t]*\n[ \t]*dockManager\.minimizeAllWindows\(\)[ \t]*\n[ \t]*\}[ \t]*\n"
    if len(re.findall(pattern, s)) != 1:
        raise RuntimeError("expected single dock minimize-all control")
    return add_glass_home(re.sub(pattern, "\n                        // " + MARK + ": window management belongs to top overflow.\n", s, count=1))
if __name__ == "__main__":
    p = Path(sys.argv[1]) / P
    original = p.read_text()
    updated = patch(original)
    if updated != original:
        p.write_text(updated)
    assert patch(updated) == updated
    print("[PASS] right dock contains app switcher without duplicate minimize-all")
