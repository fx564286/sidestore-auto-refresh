#!/usr/bin/env python3
"""V31: transactional on-device ADI -45061 recovery for pinned SideStore.

Keep the original Keychain adi.pb until an actual new provisioning round trip
returns validated Anisette headers and a nonempty replacement blob. Do not
clear other Apple credentials, signing identities or pairing records.
"""
from __future__ import annotations

import sys
from pathlib import Path

MARKER = "NRG_V31_ADI_45061_REPROVISION_V1"
TARGET = Path("SideStore/Core/Anisette/OnDeviceAnisetteManager.swift")
ORIGINAL = '''        let (anisetteData, newAdiPb) = try await provider.fetchAnisetteData(
            mode: mode,
            identifier: identifierUUID,
            existingAdiBlob: existingAdiPbData,
            headers: headers
        )

        if let freshBlob = newAdiPb {
            AnisetteConfigManager.shared.anisetteAdiBlob = freshBlob.base64EncodedString()
            debugLog("[OnDeviceAnisetteManager] [Fetch] Fresh local provisioning completed -> saved new adi.pb (\\(freshBlob.count) bytes) to Keychain")
        }

        debugLog("[OnDeviceAnisetteManager] [Fetch] SUCCESS: AnisetteData generated successfully.")
        return anisetteData
'''
REPLACEMENT = '''        // NRG_V31_ADI_45061_REPROVISION_V1:
        // -45061 means the native ADI OTP request rejected the existing
        // device provisioning. Never infer this from a bridged NSError code:
        // only the concrete AnisetteKit.AnisetteError.adiError case qualifies.
        //
        // Keep existing Keychain ADI and signing credentials untouched while
        // provisioning runs. Commit a fresh blob only after a verified
        // AnisetteDataManager fetch returns BOTH valid headers and a blob.
        do {
            let (anisetteData, newAdiPb) = try await provider.fetchAnisetteData(
                mode: mode,
                identifier: identifierUUID,
                existingAdiBlob: existingAdiPbData,
                headers: headers
            )

            if let freshBlob = newAdiPb {
                AnisetteConfigManager.shared.anisetteAdiBlob = freshBlob.base64EncodedString()
                debugLog("[OnDeviceAnisetteManager] [Fetch] Fresh local provisioning completed -> saved new adi.pb (\\(freshBlob.count) bytes) to Keychain")
            }

            debugLog("[OnDeviceAnisetteManager] [Fetch] SUCCESS: AnisetteData generated successfully.")
            return anisetteData
        } catch let originalError as AnisetteKit.AnisetteError {
            guard case .adiError(let errorCode, _) = originalError,
                  errorCode == -45061,
                  let oldAdiPbData = existingAdiPbData, !oldAdiPbData.isEmpty else {
                throw originalError
            }

            debugLog("[NRG_ADI_RECOVERY] state=staleProvisioning nativeCode=-45061 action=oneTimeReprovision previousBlob=preserved")

            // Passing nil explicitly triggers a fresh provisioning flow for
            // the SAME saved device identifier. There is only one retry,
            // and an unsuccessful retry does NOT replace the stored adi.pb.
            let (recoveredData, recoveredBlob) = try await provider.fetchAnisetteData(
                mode: mode,
                identifier: identifierUUID,
                existingAdiBlob: nil,
                headers: headers
            )
            guard let recoveredBlob, !recoveredBlob.isEmpty else {
                debugLog("[NRG_ADI_RECOVERY] state=failed cause=noNewProvisioningBlob previousBlob=preserved")
                throw originalError
            }

            let newValue = recoveredBlob.base64EncodedString()
            AnisetteConfigManager.shared.anisetteAdiBlob = newValue
            guard AnisetteConfigManager.shared.anisetteAdiBlob == newValue else {
                // Keychain write/readback failed. Restore the old blob when
                // possible; never report success with an unverified identity.
                AnisetteConfigManager.shared.anisetteAdiBlob = oldAdiPbData.base64EncodedString()
                debugLog("[NRG_ADI_RECOVERY] state=failed cause=keychainReadbackMismatch restoreAttempted=true")
                throw NSError(domain: "com.SideStore.Keychain", code: -34018)
            }
            debugLog("[NRG_ADI_RECOVERY] state=committed nativeCode=-45061 newBlobValidated=true")
            return recoveredData
        }
'''

def patch(source: str) -> str:
    if MARKER in source:
        required = (
            'errorCode == -45061',
            'existingAdiBlob: nil',
            'previousBlob=preserved',
            'state=committed',
            'AnisetteConfigManager.shared.anisetteAdiBlob == newValue',
        )
        if source.count(MARKER) != 1 or any(t not in source for t in required):
            raise ValueError("V31 ADI patch is partial or malformed")
        return source
    if source.count(ORIGINAL) != 1:
        raise ValueError("V31 expected exactly one pinned SideStore Anisette fetch block")
    if 'import AnisetteKit' not in source:
        raise ValueError("AnisetteKit import missing in pinned source")
    return source.replace(ORIGINAL, REPLACEMENT, 1)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: patch_v31_adi_45061.py <pinned-EmbeddedSideStore-root>")
    target = Path(sys.argv[1]) / TARGET
    old = target.read_text(encoding="utf-8")
    modified = patch(old)
    if modified != old:
        target.write_text(modified, encoding="utf-8")
        print("[PATCH] V31 ADI -45061 non-destructive reprovision installed")
    else:
        print("[PASS] V31 ADI -45061 reprovision already installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
