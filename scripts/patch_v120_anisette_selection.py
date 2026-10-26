#!/usr/bin/env python3
"""V120: honor a saved custom Anisette server rather than silently using the catalog."""
from pathlib import Path
import argparse
TARGET=Path("SideStore/Core/Anisette/AnisetteProvider.swift")
MARK="SCARLET_V120_ANISETTE_ROUTE"
OLD_HEAD='''        let serverUrlStrings = await AnisetteServersManager.shared.getActiveServerURLs()
        let servers = serverUrlStrings.compactMap { URL(string: $0) }
        guard !servers.isEmpty else {
            throw AnisetteError.noServersConfigured
        }

        let lastServer = UserDefaults.standard.menuAnisetteURL
        let startIndex = servers.firstIndex(where: { $0.absoluteString == lastServer }) ?? 0
'''
NEW_HEAD='''        // SCARLET_V120_ANISETTE_ROUTE: honor the V3 Custom Server URL
        // setting which older releases persisted but did not actually use.
        let v120Custom = (UserDefaults.standard.string(forKey: "textInputAnisetteURL") ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let v120Menu = UserDefaults.standard.menuAnisetteURL
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let v120Requested = v120Custom.isEmpty ? v120Menu : v120Custom
        let v120Source = !v120Custom.isEmpty ? "custom" : (!v120Menu.isEmpty ? "menu" : "catalog")
        let v120ActiveStrings = await AnisetteServersManager.shared.getActiveServerURLs()
        let v120Catalog = v120ActiveStrings.compactMap { URL(string: $0) }
        var v120Preferred: URL? = nil
        if !v120Requested.isEmpty {
            guard let parsed = URLComponents(string: v120Requested),
                  parsed.scheme?.lowercased() == "https",
                  let host = parsed.host, !host.isEmpty,
                  parsed.user == nil, parsed.password == nil,
                  parsed.query == nil, parsed.fragment == nil,
                  (parsed.path.isEmpty || parsed.path == "/"),
                  let preferred = parsed.url else {
                // Reject invalid explicit URLs instead of silently using
                // the next public server with sensitive provisioning state.
                print("[SCARLET_V120_ANISETTE_ROUTE] invalid_explicit_url=true fail_closed=true")
                throw AnisetteError.noServersConfigured
            }
            v120Preferred = preferred
        }
        let servers: [URL] = v120Preferred.map { preferred in
            [preferred] + v120Catalog.filter { $0.host?.lowercased() != preferred.host?.lowercased() }
        } ?? v120Catalog
        guard !servers.isEmpty else {
            throw AnisetteError.noServersConfigured
        }
        let startIndex = 0
        let v120ExpectedHost = servers[0].host?.lowercased() ?? ""
        let v120TargetClass = v120ExpectedHost == "sidestore.io" || v120ExpectedHost.hasSuffix(".sidestore.io")
            ? "sidestore_domain" : "other_domain"
        let v120CatalogMatch = v120Catalog.contains { $0.host?.lowercased() == v120ExpectedHost }
        print("[SCARLET_V120_ANISETTE_ROUTE] source=\(v120Source) target_class=\(v120TargetClass) catalog_match=\(v120CatalogMatch) rotation_disabled=\(UserDefaults.standard.disableAnisetteRotation)")
'''
OLD_CALL='''            servers: UserDefaults.standard.disableAnisetteRotation ? [servers[startIndex]] : servers,
            startIndex: startIndex,
'''
NEW_CALL='''            servers: UserDefaults.standard.disableAnisetteRotation ? [servers[0]] : servers,
            startIndex: startIndex,
'''
OLD_SUCCESS='''            onSuccess: { successfulServer in
                UserDefaults.standard.menuAnisetteURL = successfulServer.absoluteString
                debugLog("[AnisetteProvider] Successfully fetched Anisette data from \(successfulServer.absoluteString)")
            }
'''
NEW_SUCCESS='''            onSuccess: { successfulServer in
                // SCARLET_V120_ANISETTE_ACTUAL: header acquisition, not
                // confirmation that Apple GrandSlam accepted the login.
                let actualHost = successfulServer.host?.lowercased() ?? ""
                let actualClass = actualHost == "sidestore.io" || actualHost.hasSuffix(".sidestore.io")
                    ? "sidestore_domain" : "other_domain"
                print("[SCARLET_V120_ANISETTE_ACTUAL] source=\(v120Source) actual_class=\(actualClass) matches_selected=\(actualHost == v120ExpectedHost)")
                UserDefaults.standard.menuAnisetteURL = successfulServer.absoluteString
                debugLog("[AnisetteProvider] Successfully fetched Anisette data from \(successfulServer.absoluteString)")
            }
'''
def transform(src):
    if MARK in src or "SCARLET_V120_ANISETTE_ACTUAL" in src:
        if src.count(MARK)!=3 or src.count("SCARLET_V120_ANISETTE_ACTUAL")!=2 or NEW_HEAD not in src or NEW_SUCCESS not in src or NEW_CALL not in src:
            raise ValueError("V120 incomplete or drifted patch")
        return src
    for anchor in (OLD_HEAD,OLD_CALL,OLD_SUCCESS):
        if src.count(anchor)!=1:
            raise ValueError("V120 strict anchor mismatch")
    return src.replace(OLD_HEAD,NEW_HEAD,1).replace(OLD_CALL,NEW_CALL,1).replace(OLD_SUCCESS,NEW_SUCCESS,1)
def main():
    p=argparse.ArgumentParser()
    p.add_argument("sidestore_root",type=Path)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply",action="store_true")
    mode.add_argument("--check",action="store_true")
    a=p.parse_args()
    path=a.sidestore_root/TARGET
    before=path.read_text(encoding="utf-8")
    after=transform(before)
    if a.check:
        if after!=before or MARK not in before: p.error("V120 patch missing")
        print("SCARLET_V120_SELECTION_CHECK_OK")
    elif after!=before:
        path.write_text(after,encoding="utf-8")
        print("SCARLET_V120_SELECTION_APPLIED")
    else:
        print("SCARLET_V120_SELECTION_ALREADY_APPLIED")
if __name__=="__main__":
    main()
