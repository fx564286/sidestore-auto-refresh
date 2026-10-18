#!/usr/bin/env python3
"""V47: refresh free-team App ID inventory instead of relying on shared cache.

Apple's limit is authoritative even when the inventory-based 'available' count
is positive. This does not attempt to bypass weekly registration limits or
silently rename a user's existing application.
"""
from pathlib import Path
import sys

MARK = "NRG_V47_PORTAL_FRESH_BUDGET"
REL = Path("SideStore/Core/Operations/PipelineOperations/FetchProvisioningProfilesOperation.swift")
OLD = '''        let existing: [ALTAppID]
        if let cached = self.context.sharedContext?.appIDs {
            existing = cached
        } else {
            let fetched = try await TaskChainCoalescer.shared.coalesce(key: "fetch_app_ids_\\(team.identifier)") {
                try await DeveloperPortalProxy.shared.fetchAppIDs(for: team)
            }
            self.context.sharedContext?.appIDs = fetched
            existing = fetched
        }
'''
NEW = '''        // NRG_V47_PORTAL_FRESH_BUDGET: the process cache can be stale if
        // another installer registered IDs. Refresh once before a free-team
        // install, and share the result with the subsequent registration step.
        // Portal limits can still include weekly registrations not reflected
        // in this active inventory; 'available' is only an estimate.
        let existing = try await DeveloperPortalProxy.shared.fetchAppIDs(for: team)
        self.context.sharedContext?.appIDs = existing
        self.debugLog("[NRG_V47_APP_ID] inventory=portal_fresh capacity_is_estimate=1")
'''

def patch(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or 'capacity_is_estimate=1' not in source:
            raise RuntimeError("V47 capacity patch incomplete")
        return source
    if "NRG_V27_PROFILE_CAPACITY_PREFLIGHT" not in source:
        raise RuntimeError("V47 requires V27 capacity preflight")
    if source.count(OLD) != 1:
        raise RuntimeError(f"V47 quota preflight anchor count {source.count(OLD)}")
    return source.replace(OLD, NEW, 1)

def main(root: Path) -> None:
    target = root / REL
    before = target.read_text(encoding="utf-8")
    after = patch(before)
    if patch(after) != after:
        raise RuntimeError("V47 quota transform non-idempotent")
    if before != after:
        target.write_text(after, encoding="utf-8")
    print("[PASS] V47 free-team inventory fresh; capacity estimate not mistaken for Apple authority")

if __name__ == "__main__":
    if len(sys.argv) != 2: raise SystemExit("usage: patch_v47_portal_budget.py <pinned-EmbeddedSideStore>")
    main(Path(sys.argv[1]))
