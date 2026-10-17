#!/usr/bin/env python3
"""V33 default Apple increased-memory entitlement in the SideStore signing flow.

When absent, request increased memory on an app's App ID; preserve explicit
opt-out. Never auto-enable Extended Virtual Addressing. Check the downloaded
provisioning profile before reporting that the capability is granted.
"""
from pathlib import Path
import sys

TARGET = Path("SideStore/Core/Operations/PipelineOperations/FetchProvisioningProfilesOperation.swift")
MARKER = "NRG_V33_NATIVE_MEMORY_CAPABILITY_V1"
OLD = """        var entitlements = targetAppBundle.entitlements
        for (key, value) in context.additionalEntitlements {
            entitlements[key] = value
        }

        guard let allowedFeatures = team.type.allowedFeatures else {"""
NEW = """        var entitlements = targetAppBundle.entitlements
        for (key, value) in context.additionalEntitlements {
            entitlements[key] = value
        }
        // NRG_V33_NATIVE_MEMORY_CAPABILITY_V1: use existing SideStore session,
        // not iRAM+ or a second Apple login. Make memory entitlement the
        // default; do not override an explicit false value supplied by an IPA.
        if entitlements[ALTEntitlement.increasedMemoryLimit.rawValue] == nil {
            entitlements[ALTEntitlement.increasedMemoryLimit.rawValue] = true
        }
        // Extended Virtual Addressing stays opt-in: paid team eligibility and
        // Apple's signed provisioning profile must be checked separately.

        guard let allowedFeatures = team.type.allowedFeatures else {"""
OLD_PROFILE = """        self.debugLog("[FetchProvisioningProfiles] Provisioning profile fetched for \\(groupAppID.bundleIdentifier) (Name: \\(profile.name), Expiration: \\(String(describing: profile.expirationDate)))")
        return profile"""
NEW_PROFILE = """        self.debugLog("[FetchProvisioningProfiles] Provisioning profile fetched for \\(groupAppID.bundleIdentifier) (Name: \\(profile.name), Expiration: \\(String(describing: profile.expirationDate)))")
        // Successful App ID updates do not prove that iOS granted the right.
        // Signers must intersect requested entitlements with this signed
        // profile; never label the feature granted based on request success.
        let memoryGranted = profile.entitlements[ALTEntitlement.increasedMemoryLimit.rawValue] as? Bool == true
        self.debugLog("[NRG_MEMORY_PROFILE] increasedMemoryGranted=\\(memoryGranted)")
        return profile"""

def patch(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1 or "memoryGranted" not in source or "Extended Virtual Addressing stays opt-in" not in source:
            raise ValueError("V33 memory patch partially applied")
        return source
    begin = source.index("    func updateFeatures(for appID:")
    end = source.index("    func updateAppGroups(", begin)
    feature = source[begin:end]
    if feature.count(OLD) != 1:
        raise ValueError("V33 expected exactly one pinned feature-updater anchor")
    source = source[:begin] + feature.replace(OLD, NEW, 1) + source[end:]
    if source.count(OLD_PROFILE) != 1:
        raise ValueError("V33 expected exactly one pinned provisioning-profile anchor")
    return source.replace(OLD_PROFILE, NEW_PROFILE, 1)

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v33_sidestore_memory.py <pinned-EmbeddedSideStore-root>")
    path = Path(sys.argv[1]) / TARGET
    before = path.read_text()
    after = patch(before)
    if after != before:
        path.write_text(after)
        print("[PATCH] V33 default Increased Memory Limit and verified profile status")
    else:
        print("[PASS] V33 memory signing integration already applied")

if __name__ == "__main__":
    main()
