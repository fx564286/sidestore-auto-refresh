#!/usr/bin/env python3
"""V77: recover precisely Apple developer portal 8220 once and only for this iPhone.

Pinned SideStore ff25922e. Apply after patch_combined_service_startup.py
replaces the parent App ID algorithm. 8220 means no devices available for
team provisioning; SignInOperation registers the device but imported account
sessions or older installed apps can bypass that path. Do not modify accounts,
certificates, bundle IDs, stored guest data or profiles except the Apple team
current-device registration required for a user-requested install.
"""
from pathlib import Path
import sys

REL=Path('SideStore/Core/Operations/PipelineOperations/FetchProvisioningProfilesOperation.swift')
MARKER='LC_V77_PORTAL_8220_REGISTER_CURRENT_DEVICE'
ANCHOR='''        let profile = try await DeveloperPortalProxy.shared.downloadProvisioningProfile(for: groupAppID, deviceType: DeveloperPortalProxy.currentDeviceType, team: team)'''
REPLACEMENT='''        // LC_V77_PORTAL_8220_REGISTER_CURRENT_DEVICE: the sign-in operation
        // normally registers the current device. Imported SideStore sessions or
        // existing installations can skip that step. Only the *observed* Apple
        // portal response 8220 activates this recovery. Never infer missing
        // device registration from a generic signing or VPN error.
        let profile: ALTProvisioningProfile
        do {
            profile = try await DeveloperPortalProxy.shared.downloadProvisioningProfile(
                for: groupAppID, deviceType: DeveloperPortalProxy.currentDeviceType, team: team)
        } catch {
            // SCARLET_V95_WRAPPED_8220: DeveloperPortalProxy's
            // lcPortalSigningRequest wraps ServerError into NSError before
            // this operation receives it. The old typed-only catch never ran.
            // Only the original typed ServerError OR its authenticated,
            // request-scoped signing evidence can authorize device recovery.
            let typed8220: Bool
            if let serverError = error as? ServerError {
                if case .underlyingError(let serverCode, _) = serverError {
                    typed8220 = serverCode == 8220
                } else {
                    typed8220 = false
                }
            } else {
                let wrapped = error as NSError
                let facts = wrapped.userInfo["LCStructuredSigningContextV1"] as? [String: String]
                let source = wrapped.userInfo["LCStructuredFailureSourceV1"] as? String
                typed8220 = source == "provisioningProfileRetrieval" &&
                    facts?["typed_error"] == "sideSignServerReportedError" &&
                    facts?["server_code"] == "8220"
            }
            guard typed8220 else { throw error }
            self.debugLog("[LC_V77_PORTAL_DEVICE] stage=profile code=8220 recovery=check_team_devices source=typed_or_validated_wrapper")
            // The ID must be obtained from the currently paired, trusted iPhone.
            // Never construct a device ID, reuse an unrelated cached ID, or
            // register a device for a different signing team.
            guard let udid = try await fetchUDID(),
                  (16...80).contains(udid.count),
                  udid != "XXXXX-XXXX-XXXXX-XXXX",
                  udid.unicodeScalars.allSatisfy({
                      CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-").contains($0)
                  }) else {
                self.debugLog("[LC_V77_PORTAL_DEVICE] result=trusted_device_unavailable")
                throw OperationError.unknownUDID
            }
            let known = try await DeveloperPortalProxy.shared.fetchDevices(for: team, types: .all)
            if !known.contains(where: { $0.identifier == udid }) {
                let deviceName = await MainActor.run { UIDevice.current.name }
                _ = try await DeveloperPortalProxy.shared.registerDevice(
                    name: deviceName, identifier: udid,
                    type: DeveloperPortalProxy.currentDeviceType, team: team)
                self.debugLog("[LC_V77_PORTAL_DEVICE] result=current_device_registered team_scoped=1")
            } else {
                self.debugLog("[LC_V77_PORTAL_DEVICE] result=current_device_already_registered")
            }
            try Task.checkCancellation()
            // Exactly one profile request retry after the verified team check.
            // Preserve the original typed server error if the portal still
            // rejects the request; no unbounded retries or App ID mutations.
            profile = try await DeveloperPortalProxy.shared.downloadProvisioningProfile(
                for: groupAppID, deviceType: DeveloperPortalProxy.currentDeviceType, team: team)
            self.debugLog("[LC_V77_PORTAL_DEVICE] result=profile_retry_succeeded")
        }'''

def patch(src):
    # UIDevice belongs to UIKit; Foundation/SideSign/CoreData alone do not
    # expose it when this standalone Swift operation is compiled by Xcode.
    # Validate the import even on the idempotent second CI patch run.
    if MARKER in src:
        if src.count(MARKER)!=1 or src.count('serverCode == 8220')!=1 or \
           src.count('current_device_registered team_scoped=1')!=1 or \
           src.count('import UIKit') != 1:
            raise ValueError('V77 incomplete/duplicate patch or UIKit import missing')
        return src
    if src.count('LC_PROVISIONING_PARENT_ID_UPSTREAM_V1')!=1:
        raise ValueError('V77 needs prior pinned provenance parent-ID patch')
    if src.count(ANCHOR)!=1:
        raise ValueError(f'V77 profile fetch anchor count {src.count(ANCHOR)}')
    if 'import UIKit' not in src:
        if src.count('import Foundation\n') != 1:
            raise ValueError('V77 missing unique Foundation import anchor')
        src = src.replace('import Foundation\n',
                          'import Foundation\nimport UIKit\n', 1)
    return src.replace(ANCHOR,REPLACEMENT,1)

def main(root):
    file=root/REL
    prior=file.read_text(encoding='utf8')
    later=patch(prior)
    if patch(later)!=later:raise ValueError('V77 not idempotent')
    if prior!=later:file.write_text(later,encoding='utf8')
    print('[PASS] V77 typed 8220 portal recovery; team-scoped real UDID; one bounded profile retry')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v77_profile_8220_device_registration.py <EmbeddedSideStore>')
    main(Path(sys.argv[1]))
