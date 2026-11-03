#!/usr/bin/env python3
"""P00: do not prime LCSharedUtils's cached App Group path from early hooks.

Upstream LCSharedUtils.appGroupPath uses dispatch_once, so a diagnostic call
before the installed signed extension can open the chosen container may cache
nil for the entire process. The authoritative runtime resolver runs later
and retains its existing validation; this patch removes only this side-effect-
prone early diagnostic probe. Not a claim that SIGABRT root cause is proven.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V182_P00_DEFER_EARLY_GROUP_PROBE"
REL = Path("SideStoreSupport/SideStoreHooks.m")
OLD = '''        NSLog(@"[SIDESTORE_STARTUP] EMBEDDED_SIDESTORE_STARTUP_FIX_V1 hooks_installed host_bundle=%@ app_group_resolved=%d",
              hostBundle.bundleIdentifier, LCSharedUtils.appGroupPath != nil);'''
NEW = '''        // SCARLET_V182_P00_DEFER_EARLY_GROUP_PROBE: LCSharedUtils.appGroupPath
        // caches its first result with dispatch_once. Do not force a possibly
        // premature nil resolution just to log a boolean during hook install.
        // The runtime service logs V3SharedAppGroup.runtimeIdentity later.
        NSLog(@"[SIDESTORE_STARTUP] EMBEDDED_SIDESTORE_STARTUP_FIX_V1 hooks_installed host_bundle=%@ group_probe=deferred",
              hostBundle.bundleIdentifier);'''


def patch(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or OLD in source or "group_probe=deferred" not in source:
            raise ValueError("P00 early App Group probe patch incomplete")
        return source
    if source.count(OLD) != 1:
        raise ValueError("P00 early App Group probe anchor changed")
    return source.replace(OLD, NEW, 1)


def apply(root: Path) -> None:
    target = root / REL
    if not target.is_file() or target.is_symlink():
        raise ValueError("P00 SideStoreHooks source is unavailable")
    source = target.read_text(encoding="utf-8")
    result = patch(source)
    if patch(result) != result:
        raise ValueError("P00 App Group probe patch is not idempotent")
    if source != result:
        target.write_text(result, encoding="utf-8")
    print("[P00] no premature LCSharedUtils.appGroupPath read from early SideStore hooks")
    print("[UNVERIFIED] installed host/LiveProcess entitlement compatibility and crash root cause")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v182_p00_defer_app_group_probe.py <LiveContainer>")
    apply(Path(sys.argv[1]))
