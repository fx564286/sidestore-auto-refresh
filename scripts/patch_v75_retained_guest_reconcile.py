#!/usr/bin/env python3
"""V75: bounded, cancellation-aware scene reconciliation before in-use refusal.

Prior patch_guest_return.py installs LC_RETURN_CONTAINER_GUARD. Existing
ownership must never be ignored, unregistered or killed just to relaunch.
The first scene lookup can race with an attached LiveProcess window; give
its normal registration/reparent callback a bounded opportunity to finish.
"""
from pathlib import Path
import sys

TARGET = Path('LiveContainerSwiftUI/Models/LCAppModel.swift')
MARKER = 'LC_RETURN_V75_BOUNDED_RESUME_RECONCILE'
OLD = '''            // LC_RETURN_CONTAINER_GUARD: failed scene lookup must not duplicate a live container.
            if await MainActor.run(body: { MultitaskManager.isUsing(container: currentDataFolder) }) {
                throw "lc.container.inUse".loc + "\\nA retained guest still owns this container. Close its existing window before relaunching."
            }'''
NEW = '''            // LC_RETURN_CONTAINER_GUARD: never duplicate an active container.
            // LC_RETURN_V75_BOUNDED_RESUME_RECONCILE: LiveProcess and window
            // ownership callbacks may arrive after the first lookup. On a
            // registration hit only, retry the normal scene+Dock resume path
            // for at most 1.08 seconds. Never synthesize an owner or clear a
            // registration while a guest could still be running.
            if await MainActor.run(body: { MultitaskManager.isUsing(container: currentDataFolder) }) {
                for delayNs in [UInt64(180_000_000), 350_000_000, 550_000_000] {
                    try await Task.sleep(nanoseconds: delayNs)
                    if await bringExistingMultitaskWindowIfNeeded(dataUUID: currentDataFolder, urlScheme: urlStr) {
                        print("[LC_RETURN_V75] result=existing_scene_restored")
                        return
                    }
                    let stillOwned = await MainActor.run(body: {
                        MultitaskManager.isUsing(container: currentDataFolder)
                    })
                    if !stillOwned { break }
                }
                let stillOwned = await MainActor.run(body: {
                    MultitaskManager.isUsing(container: currentDataFolder)
                })
                if stillOwned {
                    print("[LC_RETURN_V75] result=retained_owner_unresolved safe_to_cold_launch=0")
                    throw "lc.container.inUse".loc + "\\nThe guest is still registered as running, but its window could not be restored. Close the old guest window; if none is accessible, fully quit and reopen Scarlet Crystal. Do not delete the app or its data."
                }
                print("[LC_RETURN_V75] result=registration_cleared retry_cold_launch=1")
            }'''

def patch(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1 or 'result=retained_owner_unresolved safe_to_cold_launch=0' not in source:
            raise ValueError('V75 partial or duplicated reconciliation patch')
        return source
    if source.count(OLD) != 1:
        raise ValueError('V75 expected exactly one pinned LC_RETURN_CONTAINER_GUARD')
    return source.replace(OLD, NEW, 1)

def apply(root: Path) -> None:
    target = root / TARGET
    original = target.read_text(encoding='utf-8')
    updated = patch(original)
    if updated != patch(updated):
        raise ValueError('V75 idempotency failed')
    if original != updated:
        target.write_text(updated, encoding='utf-8')
    print('[PASS] V75 bounded, cancellation-aware existing guest recovery without force cleanup')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: patch_v75_retained_guest_reconcile.py <LiveContainer source root>')
    apply(Path(sys.argv[1]))
