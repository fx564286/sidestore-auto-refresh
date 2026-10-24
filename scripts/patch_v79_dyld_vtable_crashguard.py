#!/usr/bin/env python3
"""V79: prevent LiveProcess dyld4 vtable NULL dereference on iOS 27.2.

Crash 2026-10-24 13:58:56 KST, V78 linked-image UUID
6CF93852-434F-3087-BCBE-862E60B804D8, dlopen_nolock+596:
  LDR X11, [X25, X8, LSL #3], X25=0, X8=0, FAR=0.
The pinned searchVtable() dereferences a NULL dsc-resolved vtable.
Return a bounded launch failure if mandatory private dyld lock symbols are
unavailable. Do NOT fall back to an unguarded dlopen while the extension
launch owns dyld locks: doing so risks a hang instead of a crash.
"""
from pathlib import Path
import sys

TARGET = Path("LiveContainer/Tweaks/Dyld.m")
MARKER = "SCARLET_V79_DYLD_VTABLE_NULL_GUARD"

REPLACEMENTS = (
    (
        """int searchVtable(void** vtable, void *func) {
    for(int i = 0; i < 100; ++i) {""",
        """int searchVtable(void** vtable, void *func) {
    // SCARLET_V79_DYLD_VTABLE_NULL_GUARD: iOS 27.2 DSC lookup may return NULL.
    // Never execute LDR [vtable, index] or search for a NULL member.
    if (vtable == NULL || func == NULL) return -1;
    for(int i = 0; i < 100; ++i) {""",
    ),
    (
        """        void **vtableLibSystemHelpers = litehook_find_dsc_symbol(libdyldPath, "__ZTVN5dyld416LibSystemHelpersE");
        
        if(!lockPtr) {""",
        """        void **vtableLibSystemHelpers = litehook_find_dsc_symbol(libdyldPath, "__ZTVN5dyld416LibSystemHelpersE");
        if (vtableLibSystemHelpers == NULL) {
            NSLog(@"[SCARLET_V79_DYLD] vtable=missing lock_cached=%@ unlock_cached=%@ trylock_cached=%@",
                  lockPtr != NULL ? @"yes" : @"no",
                  unlockPtr != NULL ? @"yes" : @"no",
                  trylockPtr != NULL ? @"yes" : @"no");
            if (lockPtr == NULL || unlockPtr == NULL) {
                // Mandatory lock overrides cannot be safely discovered.
                // A controlled guest-load failure is safer than dereferencing 0
                // or calling the unguarded loader with dyld locks still held.
                NSLog(@"[SCARLET_V79_DYLD] safe_abort=missing_mandatory_vtable");
                return NULL;
            }
            // Optional trylock on newer iOS may remain unpatched just as in
            // the pinned upstream trylockOffset-not-found branch.
            shouldPatchTrylock = false;
        }
        
        if(!lockPtr) {""",
    ),
    (
        """            int lockOffset = searchVtable(vtableLibSystemHelpers, lockFunc);
            NSCAssert(lockOffset != -1, @"dyld has changed: lockOffset not found in vtable");""",
        """            int lockOffset = searchVtable(vtableLibSystemHelpers, lockFunc);
            if (lockOffset < 0) {
                NSLog(@"[SCARLET_V79_DYLD] safe_abort=lock_symbol_or_vtable_missing");
                return NULL;
            }""",
    ),
    (
        """            int unlockOffset = searchVtable(vtableLibSystemHelpers, unlockFunc);
            NSCAssert(unlockOffset != -1, @"dyld has changed: unlockOffset not found in vtable");""",
        """            int unlockOffset = searchVtable(vtableLibSystemHelpers, unlockFunc);
            if (unlockOffset < 0) {
                NSLog(@"[SCARLET_V79_DYLD] safe_abort=unlock_symbol_or_vtable_missing");
                return NULL;
            }""",
    ),
    (
        """    kern_return_t ret;
    mach_vm_address_t vtablePageStart = (mach_vm_address_t)((uint64_t)lockPtr & ~(16384 - 1));""",
        """    // The private cache and the discovered vtable can both be incomplete.
    // Check all mandatory pointers before calculating a page or dereferencing.
    if (lockPtr == NULL || unlockPtr == NULL ||
        (shouldPatchTrylock && trylockPtr == NULL)) {
        NSLog(@"[SCARLET_V79_DYLD] safe_abort=missing_lock_pointer");
        return NULL;
    }
    if (*lockPtr == NULL || *unlockPtr == NULL ||
        (shouldPatchTrylock && *trylockPtr == NULL)) {
        NSLog(@"[SCARLET_V79_DYLD] safe_abort=missing_lock_implementation");
        return NULL;
    }
    kern_return_t ret;
    mach_vm_address_t vtablePageStart = (mach_vm_address_t)((uint64_t)lockPtr & ~(16384 - 1));""",
    ),
)

def patch(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1:
            raise ValueError("V79 crash guard duplicated")
        for _, new in REPLACEMENTS:
            if source.count(new) != 1:
                raise ValueError("V79 crash guard incomplete or modified")
        return source
    for old, _ in REPLACEMENTS:
        if source.count(old) != 1:
            raise ValueError("V79 pinned Dyld.m anchor missing or duplicated: " + old[:72])
    for old, new in REPLACEMENTS:
        source = source.replace(old, new, 1)
    return source

def apply(root: Path) -> None:
    target = root / TARGET
    original = target.read_text(encoding="utf-8")
    updated = patch(original)
    if patch(updated) != updated:
        raise ValueError("V79 idempotency failed")
    if updated != original:
        target.write_text(updated, encoding="utf-8")
    print("[PASS] V79 iOS 27.2 dyld4 private-vtable null crash guard")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v79_dyld_vtable_crashguard.py <LiveContainer source root>")
    apply(Path(sys.argv[1]))
