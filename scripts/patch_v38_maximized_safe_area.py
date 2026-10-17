#!/usr/bin/env python3
"""V38: keep maximized guest content clear of Dynamic Island without view scaling."""
from pathlib import Path
import sys

MARKER = "NRG_V38_MAXIMIZED_SAFE_AREA_FRAME"
OLD = """    if(self.navigationBar.hidden) {
        settings.peripheryInsets = safeAreaInsets;
        safeAreaInsets = UIEdgeInsetsZero;
    } else if(bottomWindowBar) {"""
NEW = """    if(self.navigationBar.hidden) {
        // NRG_V38_MAXIMIZED_SAFE_AREA_FRAME: the hidden host bar must not
        // let the guest's interactive content extend behind Dynamic Island.
        // Inset the actual host frame, not merely the SwiftUI visual scale.
        // Avoid double-applying the same top inset through peripheryInsets.
        settings.peripheryInsets = UIEdgeInsetsMake(0, safeAreaInsets.left,
                                                   safeAreaInsets.bottom, safeAreaInsets.right);
    } else if(bottomWindowBar) {"""

def main():
    root=Path(sys.argv[1])
    p=root/"MultitaskSupport/DecoratedAppSceneViewController.m"
    s=p.read_text()
    if MARKER in s:
        print("[PASS] V38 safe area already patched")
        return
    if s.count(OLD)!=1:
        raise SystemExit("[FAIL] V38 expected safe-area branch not found uniquely")
    p.write_text(s.replace(OLD,NEW))
    print("[PASS] V38 maximized guest safe area frame patched")

if __name__=="__main__":
    main()
