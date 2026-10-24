#!/usr/bin/env python3
"""Force pinned SideStore synchronized Icons.xcassets to be one asset catalog.

Xcode 27.2 RC reports Multiple commands produce SideStore.app/Dark.png
and SideStore.app/Contents.json because nested .imageset and .appiconset
members are scheduled as individual copies. Preserve every alternate icon.
This is an isolated CI compatibility experiment, not a source upgrade.
"""
from pathlib import Path
import sys

PROJECT = Path("AltStore.xcodeproj/project.pbxproj")
PIN = 'A8EEC8412F4B146A00F2436D /* AltStore */'
OLD_TAIL = 'explicitFileTypes = {}; explicitFolders = (); path = AltStore; sourceTree = "<group>"; };'
NEW_TAIL = 'explicitFileTypes = { "Resources/Icons.xcassets" = folder.assetcatalog; }; explicitFolders = (); path = AltStore; sourceTree = "<group>"; };'
MARKER = '"Resources/Icons.xcassets" = folder.assetcatalog'

def patch(text: str) -> str:
    if text.count(PIN + " = {") != 1:
        raise ValueError("Unexpected pinned SideStore synchronized AltStore root group")
    line = next((line for line in text.splitlines(keepends=True) if PIN + " = {" in line), "")
    if line.count(MARKER) == 1 and OLD_TAIL not in line and NEW_TAIL in line:
        return text
    if line.count(OLD_TAIL) != 1:
        raise ValueError("Pinned project structure drift: refuse asset catalog rewrite")
    return text.replace(line, line.replace(OLD_TAIL, NEW_TAIL), 1)

def apply(root: Path) -> None:
    target = root / PROJECT
    original = target.read_text(encoding="utf-8")
    modified = patch(original)
    assert patch(modified) == modified, "Not idempotent"
    if modified != original:
        target.write_text(modified, encoding="utf-8")
    print("[SCARLET_V80_XCODE27_ASSETS] Icons.xcassets compiled as a single asset catalog", flush=True)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v80_xcode27_icons_catalog.py <pinned SideStore root>")
    apply(Path(sys.argv[1]))
