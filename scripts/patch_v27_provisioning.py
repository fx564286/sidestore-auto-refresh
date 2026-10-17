#!/usr/bin/env python3
"""V27: explicit free-team App ID capacity preflight and serialized profiles.

Apply AFTER the v3 combined service startup patch, which owns the parent/child
bundle-ID rewrite. Do not delete IDs, certificates, installed apps or extensions.
"""
from pathlib import Path
import sys

MARKER = "NRG_V27_PROFILE_CAPACITY_PREFLIGHT"
SERIAL_MARKER = "NRG_V27_FREE_TEAM_SERIAL_PROVISIONING"
PATH = "SideStore/Core/Operations/PipelineOperations/FetchProvisioningProfilesOperation.swift"


def once(src, old, new, label):
    count = src.count(old)
    if count != 1:
        raise SystemExit(f"V27 provisioning {label}: anchor count {count}")
    return src.replace(old, new, 1)


def patch(root: Path):
    path = root / PATH
    source = path.read_text(encoding="utf-8")
    if MARKER in source or SERIAL_MARKER in source:
        if source.count(MARKER) != 2 or source.count(SERIAL_MARKER) != 1:
            raise SystemExit("V27 partial provisioning patch")
        print("[PASS] V27 provisioning already patched")
        return
    if "LC_PROVISIONING_PARENT_ID_UPSTREAM_V1" not in source:
        raise SystemExit("Required combined parent/extension identity fix missing")

    source = once(
        source,
        """        self.setProgress(10)

        self.debugLog("[FetchProvisioningProfiles] Preparing main provisioning profile""",
        """        self.setProgress(10)
        // NRG_V27_PROFILE_CAPACITY_PREFLIGHT: fail before creating a partial
        // set of new Apple IDs when a free team lacks the available slots.
        try await nrgV27PreflightFreeTeamCapacity(bundle: targetAppBundle,
                                                   team: team, session: session)

        self.debugLog("[FetchProvisioningProfiles] Preparing main provisioning profile""",
        "preflight invocation",
    )
    serial = """        // NRG_V27_FREE_TEAM_SERIAL_PROVISIONING: Apple free-team portal ID
        // registrations share a mutable cache. Avoid eight concurrent requests
        // racing the quota/account state or invalidating its cached snapshot.
        if team.type == .free {
            let ordered = targetAppBundle.appExtensions.sorted { $0.bundleIdentifier < $1.bundleIdentifier }
            let total = ordered.count
            for (index, ext) in ordered.enumerated() {
                try Task.checkCancellation()
                let extProfile = try await self.provisionAndFetchProfile(
                    for: ext, parentAppBundle: targetAppBundle, team: team, session: session)
                let updatedID = ext.bundleIdentifier.replacingOccurrences(
                    of: targetAppBundle.bundleIdentifier, with: effectiveBundleId)
                profiles[updatedID] = extProfile
                self.setProgress(50 + Int64(Double(index + 1) / Double(total) * 50.0))
            }
            self.debugLog("[NRG_V27_PROFILE_BUDGET] mode=serialized extensions=\\(total) profiles=\\(profiles.count)")
            return profiles
        }

"""
    source = once(source,
        "        try await withThrowingTaskGroup(of: (String, ALTProvisioningProfile).self) { group in\n",
        serial + "        try await withThrowingTaskGroup(of: (String, ALTProvisioningProfile).self) { group in\n",
        "free team sequentialization",
    )
    helper = """    // NRG_V27_PROFILE_CAPACITY_PREFLIGHT: use the same authoritative portal
    // App ID list as registration. Avoid logging raw IDs or personal details.
    private func nrgV27PreflightFreeTeamCapacity(bundle: ALTApplication,
                                                  team: ALTTeam,
                                                  session: ALTAppleAPISession) async throws {
        guard team.type == .free else { return }
        let existing: [ALTAppID]
        if let cached = self.context.sharedContext?.appIDs {
            existing = cached
        } else {
            let fetched = try await TaskChainCoalescer.shared.coalesce(key: "fetch_app_ids_\\(team.identifier)") {
                try await ALTAppleAPI.shared.fetchAppIDs(for: team, session: session)
            }
            self.context.sharedContext?.appIDs = fetched
            existing = fetched
        }
        let existingIDs = Set(existing.map { $0.bundleIdentifier.lowercased() })
        let preferredParent = await self.getPreferredBundleID(for: bundle, team: team)
        let parentID = preferredParent ?? (self.context.appendTeamID
            ? "\\(self.context.targetBundleIdentifier).\\(team.identifier)"
            : self.context.targetBundleIdentifier)
        var candidates = [parentID]
        if !self.context.useMainProfile {
            for ext in bundle.appExtensions {
                // This mirrors the pinned combined parent/suffix mapping.
                guard ext.bundleIdentifier.hasPrefix(bundle.bundleIdentifier + ".") else {
                    throw OperationError.invalidApp(
                        reason: "App extension ID does not belong to its parent; refusing registration.")
                }
                let preferred = await self.getPreferredBundleID(for: ext, team: team)
                let suffix = String(ext.bundleIdentifier.dropFirst(bundle.bundleIdentifier.count))
                candidates.append(preferred ?? (parentID + suffix))
            }
        }
        let distinct = Set(candidates.map { $0.lowercased() })
        let missing = distinct.subtracting(existingIDs).count
        let available = max(0, Team.maximumFreeAppIDs - existing.count)
        self.debugLog("[NRG_V27_PROFILE_BUDGET] type=free registered=\\(existing.count) new_required=\\(missing) available=\\(available) extension_count=\\(bundle.appExtensions.count)")
        guard missing <= available else {
            self.debugLog("[NRG_V27_PROFILE_BUDGET] decision=blocked_before_registration reason=free_team_app_id_limit")
            throw OperationError.invalidParameters(
                "Free Apple team App ID limit: \\(missing) new IDs needed, \\(available) available. Keep required LiveContainer extensions; reduce only optional extensions, reuse an existing ID, or retry after the 7-day registration window.")
        }
    }

"""
    source = once(source,
        "    private func getPreferredBundleID(for targetAppBundle: ALTApplication, team: ALTTeam) async -> String? {\n",
        helper + "    private func getPreferredBundleID(for targetAppBundle: ALTApplication, team: ALTTeam) async -> String? {\n",
        "capacity helper",
    )
    if source.count(MARKER) != 2 or source.count(SERIAL_MARKER) != 1:
        raise SystemExit("V27 provisioning markers incomplete")
    path.write_text(source, encoding="utf-8")
    print("[PASS] V27 free-team budget preflight and serialized extension provisioning")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v27_provisioning.py <EmbeddedSideStore>")
    patch(Path(sys.argv[1]))
