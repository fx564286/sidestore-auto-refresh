#!/usr/bin/env python3
"""Preserve V3 Account/Sign-In settings when porting user's Scarlet dock.

The original combined V3 service installed V3AccountSettings() into the
host Form. Latest LiveContainer refactors do not include that overlay,
and V107 correctly blocks deleting Return settings until the account
controls survive. Reinstall EXACTLY that original Form row, preserving
the unrelated Apple account/JIT/certificate settings and visual styling.
"""
from pathlib import Path
import argparse

REL = Path("LiveContainerSwiftUI/Views/Settings/LCSettingsView.swift")
SHELL = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
MARK = "SCARLET_V181_V3_ACCOUNT_SETTINGS_PRESERVED"
OLD = "            Form {\n"
NEW = (
    "            Form {\n"
    "                // SCARLET_V181_V3_ACCOUNT_SETTINGS_PRESERVED: original V3 account panel.\n"
    "                V3AccountSettings()\n"
)

def patch(source: str, shell: str) -> str:
    if "struct V3AccountSettings: View" not in shell:
        raise ValueError("canonical V3AccountSettings view implementation is missing")
    if "LCJITLessDiagnoseView()" not in source:
        raise ValueError("original JIT-Less diagnostic settings route missing")
    if MARK in source:
        if source.count(MARK) != 1 or source.count(NEW) != 1:
            raise ValueError("partial V3 account-settings port")
        return source
    if "V3AccountSettings()" in source:
        raise ValueError("other account-settings installation detected; manual review required")
    if source.count(OLD) != 1:
        raise ValueError("original host settings Form structure drifted")
    output = source.replace(OLD, NEW, 1)
    for required in ("V3AccountSettings()", "LCJITLessDiagnoseView()"):
        if required not in output:
            raise ValueError("existing account/JIT screen lost: " + required)
    return output

def main():
    p = argparse.ArgumentParser()
    p.add_argument("host", type=Path)
    args = p.parse_args()
    root = args.host.resolve()
    path = root / REL
    shell_path = root / SHELL
    if not path.is_file() or not shell_path.is_file():
        raise ValueError("required Scarlet host settings and unified shell absent")
    before = path.read_text(encoding="utf-8")
    after = patch(before, shell_path.read_text(encoding="utf-8"))
    if patch(after, shell_path.read_text(encoding="utf-8")) != after:
        raise ValueError("non-idempotent V3 Account Settings forward port")
    if before != after:
        path.write_text(after, encoding="utf-8")
    print("[PASS] V181 original V3 Account/Sign-in Settings and JIT diagnostic preserved")

if __name__ == "__main__":
    main()
