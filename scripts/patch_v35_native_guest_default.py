#!/usr/bin/env python3
"""V35: normal app launch by default; explicit multitask remains opt-in."""
from pathlib import Path
import sys
TARGET = Path("LiveContainerSwiftUI/Models/LCAppModel.swift")
MARKER = "NRG_V35_NATIVE_GUEST_DEFAULT"

def patch(source):
    if MARKER in source:
        return source
    old = '''                return uiIsMultitaskModeSpecificed == .yes ||
                (uiIsMultitaskModeSpecificed == .default && UserDefaults.standard.bool(forKey: "LCLaunchInMultitaskMode"))'''
    new = '''                // NRG_V35_NATIVE_GUEST_DEFAULT: honor explicit per-app opt-in,
                // never auto-wrap ordinary app launches in a virtual window.
                // Existing persisted global auto-multitask preferences must not
                // silently override the normal native-like launch path.
                return uiIsMultitaskModeSpecificed == .yes'''
    if source.count(old) != 1:
        raise ValueError("V35 launch decision anchor mismatch")
    return source.replace(old,new,1)

def main():
    root=Path(sys.argv[1])
    path=root/TARGET
    before=path.read_text()
    after=patch(before)
    if before!=after: path.write_text(after)
    assert MARKER in after
    print("[PASS] V35 native-like default guest launch; explicit multitask preserved")

if __name__=="__main__":
    main()
