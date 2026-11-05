#!/usr/bin/env python3
"""V188: native on-device Scarlet profile renewal with pre-install hard gates.

Patches the pinned embedded SideStore FetchProvisioningProfilesOperation. Existing
SideSign/Anisette/2FA are reused; no external login script ships inside the IPA.
The protected four App IDs and historic group remain unchanged. A certificate
that Apple has not authorized cannot silently be used for an in-place upgrade.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V188_APP_GROUP_PROFILE_PREFLIGHT"
REL = Path("SideStore/Core/Operations/PipelineOperations/FetchProvisioningProfilesOperation.swift")
BASE = "com.kdt.livecontainer.P8EZT3U5N4"
TEAM = "P8EZT3U5N4"
GROUP = "group.com.SideStore.SideStore.P8EZT3U5N4"

DECLARATION = r'''
    // SCARLET_V188_APP_GROUP_PROFILE_PREFLIGHT:
    // Native SideSign/Apple account session is the only authorization source.
    // Never fall back to a different App Group, certificate or bundle ID.
    private static let scarletV188Team = "P8EZT3U5N4"
    private static let scarletV188Group = "group.com.SideStore.SideStore.P8EZT3U5N4"
    private static let scarletV188Bundles: Set<String> = [
        "com.kdt.livecontainer.P8EZT3U5N4",
        "com.kdt.livecontainer.P8EZT3U5N4.LiveProcess",
        "com.kdt.livecontainer.P8EZT3U5N4.ShareExtension",
        "com.kdt.livecontainer.P8EZT3U5N4.LaunchAppExtension"
    ]

    func scarletV188RestoreExistingGroup(for appID: ALTAppID, team: ALTTeam) async throws -> ALTAppID {
        guard team.identifier == Self.scarletV188Team else {
            throw OperationError.invalidParameters("Scarlet team changed; stop renewal.")
        }
        let existingGroups = try await DeveloperPortalProxy.shared.fetchAppGroups(for: team)
        guard let existingGroup = existingGroups.first(where: {
            $0.groupIdentifier == Self.scarletV188Group
        }) else {
            throw OperationError.invalidParameters(
                "Scarlet's existing Apple App Group is not available; renewal blocked.")
        }

        var updated = appID
        if updated.features[.appGroups] != "true" {
            // Update only the App Group capability on the exact existing App ID.
            // Preserve all other feature settings from the fetched App ID.
            updated.features[.appGroups] = "true"
            updated = try await DeveloperPortalProxy.shared.updateAppID(updated, team: team)
        }
        // No addAppGroup / addAppID / delete / revoke operations.
        _ = try await DeveloperPortalProxy.shared.assignAppID(
            updated, to: [existingGroup], team: team)
        self.debugLog("[V188_RENEW] app_group_assigned=1 group=preserved bundle=\(appID.bundleIdentifier)")
        return updated
    }

    func scarletV188ValidateProfile(_ profile: ALTProvisioningProfile,
                                    bundleID: String, team: ALTTeam) throws {
        guard profile.bundleIdentifier == bundleID,
              profile.teamIdentifier == Self.scarletV188Team,
              team.identifier == Self.scarletV188Team,
              profile.expirationDate > Date() else {
            throw OperationError.invalidParameters(
                "Scarlet provisioning Team, Bundle ID or expiration mismatch; upgrade blocked.")
        }
        let rights = profile.entitlements
        let groups = rights["com.apple.security.application-groups"] as? [String] ?? []
        guard groups.contains(Self.scarletV188Group) else {
            throw OperationError.invalidParameters(
                "Apple returned a profile without Scarlet's original App Group; upgrade blocked.")
        }
        guard let keychains = rights["keychain-access-groups"] as? [String],
              !keychains.isEmpty else {
            throw OperationError.invalidParameters(
                "Apple returned a profile without Keychain access; upgrade blocked.")
        }
        if bundleID == "com.kdt.livecontainer.P8EZT3U5N4",
           rights["com.apple.developer.kernel.increased-memory-limit"] as? Bool != true {
            throw OperationError.invalidParameters(
                "Apple did not grant Scarlet's existing memory entitlement; upgrade blocked.")
        }
        guard let signingSerial = self.context.targetSigningCertificate?.serialNumber.lowercased(),
              profile.certificates.contains(where: {
                  $0.serialNumber.lowercased() == signingSerial
              }) else {
            // A P12 can be cryptographically valid yet absent from Apple's newly
            // issued provisioning profile. Do not revoke/change identities here.
            throw OperationError.invalidParameters(
                "Selected signing certificate is not authorized by the renewed Apple profile. " +
                "Use an existing, Apple-authorized signable certificate; do not revoke automatically.")
        }
        self.debugLog("[V188_RENEW] profile_valid=1 group=preserved cert_authorized=1")
    }

'''

OLD_GROUP = '''        let groupAppID = try await self.updateAppGroups(for: updatedAppID, targetAppBundle: targetAppBundle, team: team)
'''
NEW_GROUP = '''        let scarletProtected = team.identifier == Self.scarletV188Team &&
            Self.scarletV188Bundles.contains(bundleID)
        let groupAppID: ALTAppID
        if scarletProtected {
            groupAppID = try await self.scarletV188RestoreExistingGroup(
                for: updatedAppID, team: team)
        } else {
            groupAppID = try await self.updateAppGroups(
                for: updatedAppID, targetAppBundle: targetAppBundle, team: team)
        }
'''

OLD_RETURN = '''        self.debugLog("[FetchProvisioningProfiles] Provisioning profile fetched for \\(groupAppID.bundleIdentifier) (Name: \\(profile.name), Expiration: \\(String(describing: profile.expirationDate)))")
        return profile
'''
NEW_RETURN = '''        self.debugLog("[FetchProvisioningProfiles] Provisioning profile fetched for \\(groupAppID.bundleIdentifier) (Name: \\(profile.name), Expiration: \\(String(describing: profile.expirationDate)))")
        if scarletProtected {
            try self.scarletV188ValidateProfile(profile, bundleID: bundleID, team: team)
        }
        return profile
'''

OLD_OVERRIDE = '''        if let overrideProfile = self.context.overrideProvisioningProfile {
'''
NEW_OVERRIDE = '''        if let overrideProfile = self.context.overrideProvisioningProfile {
            if self.context.targetBundleIdentifier == "com.kdt.livecontainer.P8EZT3U5N4" {
                throw OperationError.invalidParameters(
                    "Scarlet in-place renewal cannot bypass Apple profile authorization with a manual override.")
            }
'''

def replace_once(src: str, old: str, new: str, label: str) -> str:
    count = src.count(old)
    if count != 1:
        raise ValueError(f"V188 {label}: expected exactly one anchor; found {count}")
    return src.replace(old, new, 1)

def patch(src: str) -> str:
    if MARK in src:
        for evidence in (MARK, "scarletV188ValidateProfile", "scarletV188RestoreExistingGroup",
                         "certificate is not authorized", "scarletProtected"):
            if evidence not in src:
                raise ValueError("V188 partially patched: " + evidence)
        return src
    if "class FetchProvisioningProfilesOperation:" not in src:
        raise ValueError("unexpected upstream SideStore provisioning operation")
    src = replace_once(src, OLD_OVERRIDE, NEW_OVERRIDE, "override fail-closed")
    src = replace_once(src, OLD_GROUP, NEW_GROUP, "existing group selection")
    src = replace_once(src, OLD_RETURN, NEW_RETURN, "post-download profile validation")
    anchor = "private extension FetchProvisioningProfilesOperation{\n"
    src = replace_once(src, anchor, anchor + DECLARATION, "native helper methods")
    return src

def apply(root: Path):
    path = root / REL
    if not path.is_file() or path.is_symlink():
        raise ValueError("missing upstream SideStore provisioning operation")
    current = path.read_text(encoding="utf-8")
    candidate = patch(current)
    if patch(candidate) != candidate:
        raise ValueError("V188 idempotence failure")
    if candidate != current:
        path.write_text(candidate, encoding="utf-8")
    print("[PASS] V188 in-app App Group preservation + profile/cert gates")
    print("[INFO] No certificate replacement, App ID registration or device installation")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_v188_native_refresh.py <EmbeddedSideStore>")
    apply(Path(sys.argv[1]))
