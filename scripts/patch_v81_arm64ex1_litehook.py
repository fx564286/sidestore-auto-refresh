#!/usr/bin/env python3
"""V81: restore litehook arm64e.x1 dyld shared-cache discovery on iOS 27.2 RC.

The pinned LiveContainer commit 12377cf includes litehook 8025e0c,
whose litehook_locate_dsc suffixes omit "_arm64e_x1". Upstream litehook
a7e9f599 adds exactly one entry, preceding "_arm64e".
Apply only that upstream change, preserving every existing LC and V79/V80 hook.
Reference: LiveContainer/LiveContainer commit 4dbe0f9.
"""
from pathlib import Path
import sys

RELATIVE = Path("litehook/src/litehook.c")
MARKER = '"_arm64e_x1",'
ORIGINAL = '''\t\tconst char *suffixCandidates[] = {
\t\t\t"_arm64e",
'''
PATCHED = '''\t\tconst char *suffixCandidates[] = {
\t\t\t"_arm64e_x1",
\t\t\t"_arm64e",
'''

def patch(source: str) -> str:
    if source.count(MARKER) == 1:
        if source.count(PATCHED) != 1:
            raise ValueError("Unexpected arm64e_x1 litehook placement; fail closed")
        return source
    if MARKER in source or source.count(ORIGINAL) != 1:
        raise ValueError("Pinned litehook source drift; expected unpatched 8025e0c suffixes")
    return source.replace(ORIGINAL, PATCHED, 1)

def apply(root: Path) -> None:
    target = root / RELATIVE
    original = target.read_text(encoding="utf-8")
    updated = patch(original)
    assert patch(updated) == updated
    if updated != original:
        target.write_text(updated, encoding="utf-8")
    print("[PASS] V81 litehook arm64e_x1 dyld shared-cache suffix compatibility")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v81_arm64ex1_litehook.py <pinned LiveContainer source root>")
    apply(Path(sys.argv[1]))
