#!/usr/bin/env python3
"""Scarlet V121: strict V3 diagnostics for explicitly known V3 Anisette servers.

Avoid hiding V3 /get_headers failures behind an unrelated v1 root GET.
Limit behavior change to known V3 hosts; preserve all existing adi.pb and
account/keychain state. No headers, identifiers or response bodies are logged.
"""
import argparse
from pathlib import Path

TARGET=Path("Sources/Anisette/RemoteAnisetteDataProvider.swift")
MARK="v121KnownV3Hosts"
ANCHOR="""        // 1. If adiPb is present, attempt v3 /v3/get_headers
        if !adiPb.isEmpty {
"""
INJECT="""        // SCARLET_V121_ANISETTE_V3: known V3 servers must not silently
        // downgrade to v1 after a V3 failure using an existing ADI blob.
        // This is diagnostic and preserves the original ADI and identifier.
        let v121KnownV3Hosts: Set<String> = ["new.ani.sidestore.io", "mac-ani.jkcoxson.com"]
        if !adiPb.isEmpty && v121KnownV3Hosts.contains(serverURL.host?.lowercased() ?? "") {
            let v121Base = serverURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
            guard let v121URL = URL(string: "\\(v121Base)/\\(Constants.URLs.v3GetHeaders)") else {
                print("[SCARLET_V121_ANISETTE_V3] stage=construct failed=true")
                throw AnisetteError.invalidURL
            }
            var v121Request = URLRequest(url: v121URL)
            v121Request.timeoutInterval = Constants.Anisette.remoteRequestTimeout
            v121Request.httpMethod = "POST"
            v121Request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            v121Request.cachePolicy = .reloadIgnoringLocalCacheData
            v121Request.httpBody = try JSONSerialization.data(withJSONObject: [
                "identifier": cleanIdentifier,
                "adi_pb": Data(adiPb).base64EncodedString()
            ])
            let v121Packet: (Data, URLResponse)
            do {
                v121Packet = try await URLSession.shared.data(for: v121Request)
            } catch {
                let code = (error as NSError).code
                print("[SCARLET_V121_ANISETTE_V3] stage=transport failed=true code=\\(code)")
                throw error
            }
            let (v121Data, v121Response) = v121Packet
            guard let v121HTTP = v121Response as? HTTPURLResponse else {
                print("[SCARLET_V121_ANISETTE_V3] stage=http response_missing=true")
                throw AnisetteError.badServerResponse(statusCode: -1, payload: "V3 response was not HTTP")
            }
            print("[SCARLET_V121_ANISETTE_V3] stage=v3_get_headers http=\\(v121HTTP.statusCode) response_bytes=\\(v121Data.count)")
            guard (200...299).contains(v121HTTP.statusCode) else {
                throw AnisetteError.badServerResponse(statusCode: v121HTTP.statusCode, payload: "V3 get_headers HTTP failure; body intentionally not logged")
            }
            guard let v121JSON = (try? JSONSerialization.jsonObject(with: v121Data)) as? [String: String] else {
                print("[SCARLET_V121_ANISETTE_V3] stage=decode failed=true")
                throw AnisetteError.invalidAnisetteData
            }
            if v121JSON["result"] == "GetHeadersError" {
                print("[SCARLET_V121_ANISETTE_V3] stage=get_headers result=rejected")
                throw AnisetteError.badServerResponse(statusCode: v121HTTP.statusCode, payload: "V3 get_headers rejected stored ADI or identifier; response body withheld")
            }
            do {
                let v121Headers = try AnisetteDataResponse(from: v121JSON)
                print("[SCARLET_V121_ANISETTE_V3] stage=decode success=true")
                return v121Headers
            } catch {
                print("[SCARLET_V121_ANISETTE_V3] stage=headers invalid=true")
                throw error
            }
        }
"""
def transform(src: str) -> str:
    if INJECT in src:
        return src
    if MARK in src:
        raise ValueError("V121 partial patch: refuse")
    if src.count(ANCHOR) != 1:
        raise ValueError("V121 unexpected pinned SideSign source")
    return src.replace(ANCHOR, INJECT + ANCHOR, 1)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("sidesign_root",type=Path)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply",action="store_true")
    mode.add_argument("--check",action="store_true")
    args=parser.parse_args()
    path=args.sidesign_root/TARGET
    before=path.read_text(encoding="utf-8")
    after=transform(before)
    if args.check:
        if after!=before or INJECT not in before:
            parser.error("V121 trace patch not present")
        print("SCARLET_V121_ANISETTE_CHECK_OK")
    elif after!=before:
        path.write_text(after,encoding="utf-8")
        print("SCARLET_V121_ANISETTE_APPLIED")
    else:
        print("SCARLET_V121_ANISETTE_ALREADY_APPLIED")

if __name__=="__main__":
    main()
