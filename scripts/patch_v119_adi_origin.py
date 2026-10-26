#!/usr/bin/env python3
"""V119: classify Anisette provenance without modifying accounts or ADI.

V118 already ruled out missing Anisette fields, stale request clocks and
GrandSlam connection reuse. The remaining question is provider/ADI provenance.
This is read-only instrumentation; user-selected servers and overrides stay put.
"""
from pathlib import Path
import argparse

MARK = "SCARLET_V119_ADI_ORIGIN"
TARGET = Path("SideStore/Core/Anisette/AnisetteProvider.swift")
ENTRY = '''    static func fetch(handler: AnisetteServerHandler? = nil) async throws -> ALTAnisetteData {
'''
ROUTE = '''        // SCARLET_V119_ADI_ORIGIN: classify, never output server URLs,
        // machine identifiers, Apple IDs, passwords, ADI blobs or tokens.
        let v119OnDevice = UserDefaults.standard.useOnDeviceAnisette
        let v119RotationDisabled = UserDefaults.standard.disableAnisetteRotation
        let v119ExistingAdi = AnisetteConfigManager.shared.anisetteAdiBlob
        let v119Config = await AnisetteConfigManager.shared.loadConfig()
        let v119DeclaredClass = v119Config.clientInfo.contains("<Android;") ? "android"
            : v119Config.clientInfo.contains("<Windows;") ? "windows"
            : v119Config.clientInfo.contains("<Mac") ? "mac" : "other"
        let v119SelectedURL = UserDefaults.standard.menuAnisetteURL
        let v119Names = await AnisetteServersManager.shared.loadLocalServers()
        let v119SelectedName = v119Names.first(where: { $0.address == v119SelectedURL })?.name.lowercased() ?? ""
        let v119CatalogHint = v119SelectedName.contains("mac")
            || (v119SelectedName.contains("sidestore") && v119SelectedName.contains("new"))
            ? "mac_named" : (v119SelectedName.contains("android") ? "android_named" : "unclassified")
        // Catalog names are only hints, not proof of native ADI library.
        print("[SCARLET_V119_ADI_ORIGIN] stage=fetch mode=\(v119OnDevice ? "ondevice" : "remote") existing_adi=\(v119ExistingAdi?.isEmpty == false) rotation_disabled=\(v119RotationDisabled) config_family=\(v119DeclaredClass) server_catalog_hint=\(v119CatalogHint) routing_override=\(v119Config.customRoutingInfo?.isEmpty == false)")
'''
REMOTE = '''        if let freshBlob = newAdiBlob {
            AnisetteConfigManager.shared.anisetteAdiBlob = freshBlob.base64EncodedString()
        }

        return anisetteData
'''
REMOTE_NEW = '''        // SCARLET_V119_ADI_ORIGIN: successful header acquisition is not
        // Apple acceptance. Do not claim matched provenance without proof.
        let v119ActiveURL = UserDefaults.standard.menuAnisetteURL
        let v119KnownServers = await AnisetteServersManager.shared.loadLocalServers()
        let v119ActiveName = v119KnownServers.first(where: { $0.address == v119ActiveURL })?.name.lowercased() ?? ""
        let v119ActiveHint = v119ActiveName.contains("mac")
            || (v119ActiveName.contains("sidestore") && v119ActiveName.contains("new"))
            ? "mac_named" : (v119ActiveName.contains("android") ? "android_named" : "unclassified")
        let v119ActualFamily = anisetteData.clientInfo.contains("<Android;") ? "android"
            : anisetteData.clientInfo.contains("<Windows;") ? "windows"
            : anisetteData.clientInfo.contains("<Mac") ? "mac" : "other"
        print("[SCARLET_V119_ADI_RESULT] mode=remote header_family=\(v119ActualFamily) successful_server_hint=\(v119ActiveHint) new_adi=\(newAdiBlob?.isEmpty == false) reused_prior_adi=\(existingBlob?.isEmpty == false)")
''' + REMOTE

def transform(source: str) -> str:
    if MARK in source:
        if (source.count(MARK) != 2 or ROUTE not in source
                or REMOTE_NEW not in source):
            raise ValueError('V119 partial provenance instrumentation')
        return source
    if source.count(ENTRY) != 1 or source.count(REMOTE) != 1:
        raise ValueError('V119 strict SideStore source anchor mismatch')
    return source.replace(ENTRY, ENTRY + ROUTE, 1).replace(REMOTE, REMOTE_NEW, 1)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('sidestore_root',type=Path)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--apply',action='store_true')
    mode.add_argument('--check',action='store_true')
    a=p.parse_args()
    target=a.sidestore_root/TARGET
    before=target.read_text(encoding='utf-8')
    after=transform(before)
    if a.check:
        if after != before or MARK not in before:
            p.error('V119 provenance patch missing')
        print('SCARLET_V119_ORIGIN_CHECK_OK')
    elif after != before:
        target.write_text(after,encoding='utf-8')
        print('SCARLET_V119_ORIGIN_APPLIED')
    else:
        print('SCARLET_V119_ORIGIN_ALREADY_APPLIED')

if __name__=='__main__':
    main()
