#!/usr/bin/env python3
"""V122: preserve global ADI while reprovisioning only an explicit V3 server.

This source transform applies after V119/V120. On a *typed* V121 V3
GetHeadersError response, it attempts one in-memory fresh provisioning.
The old global adi.pb stays untouched. Store a successful server-scoped blob
in a new Keychain slot, with readback verification, never in the global slot.
"""
import argparse
from pathlib import Path

TARGET=Path("SideStore/Core/Anisette/AnisetteProvider.swift")
KEYCHAIN_TARGET=Path("AltStore/Core/Components/Keychain.swift")
MARK="SCARLET_V122_SCOPED_ADI"
ANCHOR="""        let headers = await AnisetteConfigManager.shared.makeRequestHeaders()

        let (anisetteData, newAdiBlob) = try await provider.fetchAnisetteDataWithFailover(
"""
ADDITION="""        // SCARLET_V122_SCOPED_ADI: Anisette provisioning state is server-specific.
        // Only an explicitly pinned V3 host with rotation disabled may recover.
        // Never change Keychain.adiPb (legacy/global), identifier, Apple auth or
        // signing identities; successful blobs use independent Keychain slots.
        let v122Host = v120Preferred?.host?.lowercased() ?? ""
        let v122Scope = UserDefaults.standard.disableAnisetteRotation &&
            (v122Host == "new.ani.sidestore.io" || v122Host == "mac-ani.jkcoxson.com")
        if v122Scope {
            let v122Stored = v122Host == "new.ani.sidestore.io"
                ? Keychain.shared.scarletV122SideStoreAdiPb
                : Keychain.shared.scarletV122MacAdiPb
            let v122ScopedBlob = v122Stored.flatMap { Data(base64Encoded: $0) }
            let v122Candidate = v122ScopedBlob ?? existingBlob
            print("[SCARLET_V122_SCOPED_ADI] mode=single_v3 prior_scoped=\\(v122ScopedBlob?.isEmpty == false) legacy_present=\\(existingBlob?.isEmpty == false) original_preserved=true")

            func v122CommitScoped(_ newData: Data) throws {
                guard !newData.isEmpty else {
                    throw SideSign.AnisetteError.invalidAnisetteData
                }
                let encoded = newData.base64EncodedString()
                if v122Host == "new.ani.sidestore.io" {
                    Keychain.shared.scarletV122SideStoreAdiPb = encoded
                    guard Keychain.shared.scarletV122SideStoreAdiPb == encoded else {
                        throw SideSign.AnisetteError.providerNotReady("Scoped V3 Keychain verification failed")
                    }
                } else {
                    Keychain.shared.scarletV122MacAdiPb = encoded
                    guard Keychain.shared.scarletV122MacAdiPb == encoded else {
                        throw SideSign.AnisetteError.providerNotReady("Scoped V3 Keychain verification failed")
                    }
                }
                print("[SCARLET_V122_SCOPED_ADI] state=committed scoped=true legacy_preserved=true")
            }

            do {
                let (v122Data, v122Fresh) = try await provider.fetchAnisetteData(
                    mode: .remote(server: servers[0]),
                    identifier: identifier,
                    existingAdiBlob: v122Candidate,
                    headers: headers
                )
                if let v122Fresh, !v122Fresh.isEmpty {
                    try v122CommitScoped(v122Fresh)
                }
                print("[SCARLET_V122_SCOPED_ADI] state=header_success reprovision=false")
                return v122Data
            } catch let error as SideSign.AnisetteError {
                guard case .badServerResponse(let http, let payload) = error,
                      http == 200,
                      payload.hasPrefix("V3 get_headers rejected"),
                      v122Candidate?.isEmpty == false else {
                    throw error
                }
                // This is not a blanket retry for network/Apple/GSA errors:
                // only the verified V3 rejection triggers one nil-ADI attempt.
                print("[SCARLET_V122_SCOPED_ADI] state=v3_rejected action=one_shot_in_memory_provision legacy_preserved=true")
                let (freshHeaders, freshBlob) = try await provider.fetchAnisetteData(
                    mode: .remote(server: servers[0]),
                    identifier: identifier,
                    existingAdiBlob: nil,
                    headers: headers
                )
                guard let freshBlob, !freshBlob.isEmpty else {
                    print("[SCARLET_V122_SCOPED_ADI] state=failed reason=no_new_blob legacy_preserved=true")
                    throw error
                }
                try v122CommitScoped(freshBlob)
                print("[SCARLET_V122_SCOPED_ADI] state=header_success reprovision=true")
                return freshHeaders
            }
        }

"""
KEYCHAIN_ANCHOR="""    @KeychainItem(key: "adiPb")
    public var adiPb: String?
"""
KEYCHAIN_ADDITION="""    // SCARLET_V122_SCOPED_ADI: independent per-V3-provider provisioning.
    // Never overwrite or migrate existing adiPb without explicit user action.
    @KeychainItem(key: "scarletV122SideStoreAdiPb")
    public var scarletV122SideStoreAdiPb: String?

    @KeychainItem(key: "scarletV122MacAdiPb")
    public var scarletV122MacAdiPb: String?
"""
def transform_provider(src: str) -> str:
    if MARK in src:
        if ADDITION not in src: raise ValueError("partial V122 provider patch")
        return src
    if src.count(ANCHOR)!=1 or "SCARLET_V120_ANISETTE_ROUTE" not in src:
        raise ValueError("unexpected V120 provider base")
    return src.replace(ANCHOR,ANCHOR.replace("\n        let (anisetteData", "\n"+ADDITION+"        let (anisetteData"),1)

def transform_keychain(src: str) -> str:
    if MARK in src:
        if KEYCHAIN_ADDITION not in src: raise ValueError("partial V122 Keychain patch")
        return src
    if src.count(KEYCHAIN_ANCHOR)!=1: raise ValueError("unexpected pinned Keychain base")
    return src.replace(KEYCHAIN_ANCHOR,KEYCHAIN_ANCHOR+"\n"+KEYCHAIN_ADDITION,1)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("sidestore_root",type=Path)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply",action="store_true")
    mode.add_argument("--check",action="store_true")
    a=p.parse_args()
    for path,transform in ((TARGET,transform_provider),(KEYCHAIN_TARGET,transform_keychain)):
        dest=a.sidestore_root/path
        before=dest.read_text(encoding="utf-8")
        after=transform(before)
        if a.check:
            if before!=after or MARK not in before:
                p.error("V122 missing: "+str(path))
        elif after!=before:
            dest.write_text(after,encoding="utf-8")
    print("SCARLET_V122_SCOPED_ADI_"+("CHECK_OK" if a.check else "APPLIED"))
if __name__=="__main__":
    main()
