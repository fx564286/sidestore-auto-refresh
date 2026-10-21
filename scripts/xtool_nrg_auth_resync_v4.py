#!/usr/bin/env python3
"""Conditional one-shot Anisette hsc=434 resync for isolated xtool 1.22.2.

SideInstaller-compatible behavior only when Apple sends -22421 + hsc 434 +
X-Apple-I-MD-DATA on GSA init. Never replays complete, app tokens or 2FA.
Never removes provisioning data, auth token, certificate, app, or profile.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess

PIN = "65bf3cc5a1240fea53ac0748d29a01878222a6ce"
MARKER = "NRG_XTOOL_GSA_HSC434_V4"
TRACE = "NRG_XTOOL_AUTH_TRACE_V2"
V3 = "NRG_XTOOL_SIDESTORE_CPD_V3"

OPS = Path("Sources/XKit/GrandSlam/Requests/GrandSlamOperationRequest.swift")
OMNI = Path("Sources/XKit/GrandSlam/Anisette/OmnisetteADIProvider.swift")
ADI = Path("Sources/XKit/GrandSlam/Anisette/ADIDataProvider.swift")
CLIENT = Path("Sources/XKit/GrandSlam/GrandSlamClient.swift")

PATCHES: dict[Path,list[tuple[str,str]]] = {
    OPS: [
        ("""struct GrandSlamOperationError: Error, LocalizedError {
    let code: Int
    let message: String
""", """struct GrandSlamOperationError: Error, LocalizedError {
    let code: Int
    let message: String
    // NRG_XTOOL_GSA_HSC434_V4: private typed metadata, never log sim.
    let hsc: Int?
    let resyncData: Data?
"""),
        ("""    struct Status: Decodable {
        let errorCode: Int
        let errorMessage: String

        private enum CodingKeys: String, CodingKey {
            case errorCode = "ec"
            case errorMessage = "em"
        }
    }""",
"""    struct Status: Decodable {
        let errorCode: Int
        let errorMessage: String
        let hsc: Int?
        let resyncData: Data?

        private enum CodingKeys: String, CodingKey {
            case errorCode = "ec"
            case errorMessage = "em"
            case hsc
            case resyncData = "X-Apple-I-MD-DATA"
        }

        init(from decoder: Decoder) throws {
            let c = try decoder.container(keyedBy: CodingKeys.self)
            errorCode = try c.decode(Int.self, forKey: .errorCode)
            errorMessage = try c.decode(String.self, forKey: .errorMessage)
            hsc = try c.decodeIfPresent(Int.self, forKey: .hsc)
            // Apple can represent sim as plist data or a base64 string.
            if let data = try? c.decode(Data.self, forKey: .resyncData) {
                resyncData = data
            } else if let encoded = try? c.decode(String.self, forKey: .resyncData) {
                resyncData = Data(base64Encoded: encoded)
            } else {
                resyncData = nil
            }
        }
    }"""),
        ("""            throw GrandSlamOperationError(code: status.errorCode, message: status.errorMessage)""",
"""            throw GrandSlamOperationError(
                code: status.errorCode,
                message: status.errorMessage,
                hsc: status.hsc,
                resyncData: status.resyncData
            )"""),
    ],
    OMNI: [
        ("""import Foundation
import Dependencies
""", """import Foundation
import Dependencies
import Crypto
"""),
        ("""}

private final class OmnisetteProvisioningSession""",
"""    // NRG_XTOOL_GSA_HSC434_V4: server applies Apple's resync payload and
    // issues a new OTP for the same already-provisioned identity.
    func requestOTPResync(
        userID: UUID,
        routingInfo: inout UInt64,
        provisioningInfo: Data,
        sim: Data
    ) async throws -> (machineID: Data, otp: Data) {
        guard !sim.isEmpty && sim.count <= 65536 else {
            throw NRGAnisetteResyncError.invalidPayload
        }
        struct Request: Encodable {
            let identifier: Data
            let adiPb: Data
            let sim: String
            let deviceId: String
            let mdLu: String
        }
        struct Response: Decodable {
            let machineID: Data
            let otp: Data
            let rinfo: String
            enum CodingKeys: String, CodingKey {
                case machineID = "X-Apple-I-MD-M"
                case otp = "X-Apple-I-MD"
                case rinfo = "X-Apple-I-MD-RINFO"
            }
        }
        let rawID = userID.rawBytes
        let mdLu = SHA256.hash(data: rawID)
            .map { String(format: "%02x", $0) }.joined()
        let body = try Self.encoder.encode(Request(
            identifier: rawID,
            adiPb: provisioningInfo,
            sim: sim.base64EncodedString(),
            deviceId: userID.uuidString.lowercased(),
            mdLu: mdLu
        ))
        var request = HTTPRequest(url: url.appendingPathComponent("v3/get_headers"))
        request.method = .post
        request.headerFields[.contentType] = "application/json"
        let result = try await client.makeRequest(request, body: body).body
        let decoded = try Self.decoder.decode(Response.self, from: result)
        if let rinfo = UInt64(decoded.rinfo) {
            routingInfo = rinfo
        }
        return (decoded.machineID, decoded.otp)
    }
}

private final class OmnisetteProvisioningSession"""),
    ],
    ADI: [
        ("""public protocol RawADIProvider: Sendable {""",
"""// NRG_XTOOL_GSA_HSC434_V4: bounded optional resync, only for compatible remote v3.
public enum NRGAnisetteResyncError: Error {
    case unsupported
    case invalidPayload
}

public protocol RawADIProvider: Sendable {"""),
        ("""    public var providerID: String? { Self.providerID }

    public func provisioningData() -> ProvisioningData? {""",
"""    public var providerID: String? { Self.providerID }

    // NRG_XTOOL_GSA_HSC434_V4: use existing isolated provisioning state.
    // Do not reprovision, reset, replace account identity or touch certificates.
    public func nrgResync(sim: Data) async throws -> AnisetteData {
        guard DeviceInfo.nrgSideStoreAuth,
              let remote = rawProvider as? OmnisetteADIProvider,
              let current = provisioningData()
        else { throw NRGAnisetteResyncError.unsupported }
        var routing = current.routingInfo
        let (mid, otp) = try await remote.requestOTPResync(
            userID: localUserUID,
            routingInfo: &routing,
            provisioningInfo: current.adiPb,
            sim: sim
        )
        return AnisetteData(
            clientTime: Date(),
            routingInfo: routing,
            machineID: mid.base64EncodedString(),
            localUserID: self.localUserID,
            oneTimePassword: otp.base64EncodedString(),
            deviceID: localUserUID.uuidString
        )
    }

    public func provisioningData() -> ProvisioningData? {"""),
    ],
    CLIENT: [
        ("""                if tracing {
                    print("[NRG_AUTH_TRACE] phase=\\(phase) http=\\(resp.response.status.code) gsa_code=\\(error.code)")
                }""",
"""                if tracing {
                    print("[NRG_AUTH_TRACE] phase=\\(phase) http=\\(resp.response.status.code) gsa_code=\\(error.code)")
                    if error.code == -22421 {
                        let hscText = error.hsc.map { String($0) } ?? "none"
                        print("[NRG_AUTH_TRACE] phase=\\(phase) hsc=\\(hscText) sim_present=\\(error.resyncData != nil)")
                    }
                }"""),
        ("""                throw error
            } catch {
                if tracing {
                    print("[NRG_AUTH_TRACE] phase=\\(phase) http=\\(resp.response.status.code) result=decode_failed")
                }
                throw error
            }""",
"""                // NRG_XTOOL_GSA_HSC434_V4: first-time Windows ADI machines
                // receive hsc 434 and sim. Only retry SRP init ONCE with
                // server-resynchronized OTP. Never retry password/2FA requests.
                if DeviceInfo.nrgSideStoreAuth,
                   request is GrandSlamAuthInitRequest,
                   error.code == -22421,
                   error.hsc == 434,
                   let sim = error.resyncData,
                   !sim.isEmpty, sim.count <= 65536,
                   let adi = anisetteDataProvider as? ADIDataProvider {
                    if tracing {
                        print("[NRG_AUTH_TRACE] phase=init hsc=434 anisette_resync=started")
                    }
                    let refreshed = try await adi.nrgResync(sim: sim)
                    let retryMethod = request.method(
                        deviceInfo: deviceInfo, anisetteData: refreshed)
                    let retryBody: Data? = switch retryMethod {
                    case .get: nil
                    case .post(let data):
                        try PropertyListSerialization.data(
                            fromPropertyList: data, format: .xml, options: 0)
                    }
                    // httpRequest retains the agreed Windows headers; only cpd
                    // changes. A fresh connection sends the one bounded replay.
                    let retried = try await httpClient.withEphemeralClient {
                        try await $0.makeRequest(httpRequest, body: retryBody)
                    }
                    let decoded = try R.Decoder.decode(data: retried.body)
                    if tracing {
                        print("[NRG_AUTH_TRACE] phase=init anisette_resync=success")
                    }
                    return decoded
                }
                throw error
            } catch {
                if tracing {
                    print("[NRG_AUTH_TRACE] phase=\\(phase) http=\\(resp.response.status.code) result=decode_failed")
                }
                throw error
            }"""),
    ]
}


def transform(source: str, pairs: list[tuple[str,str]], name: str) -> str:
    updated = source
    for old, new in pairs:
        if updated.count(new) == 1:
            continue
        if updated.count(old) != 1:
            raise ValueError(f"{name}: expected exact pinned anchor")
        updated = updated.replace(old, new, 1)
    return updated


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("xtool_checkout", type=Path)
    selection = p.add_mutually_exclusive_group(required=True)
    selection.add_argument("--apply", action="store_true")
    selection.add_argument("--check", action="store_true")
    args = p.parse_args()
    root = args.xtool_checkout.resolve()
    if not (root / ".git").is_dir():
        p.error("Require isolated git source checkout")
    sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if sha != PIN:
        p.error("Only pinned xtool 1.22.2 source is supported")
    if V3 not in (root / CLIENT).read_text():
        p.error("SideInstaller CPD V3 prerequisite not installed")
    if TRACE not in (root / CLIENT).read_text():
        p.error("Safe phase trace V2 prerequisite not installed")
    results = {}
    for rel, changes in PATCHES.items():
        f = root / rel
        before = f.read_text(encoding="utf-8")
        after = transform(before, changes, str(rel))
        if args.check and (after != before or MARKER not in before):
            p.error(f"Missing or partial hsc 434 patch in {rel}")
        results[f] = (before, after)
    if args.apply:
        for f,(before,after) in results.items():
            if before != after:
                f.write_text(after, encoding="utf-8")
    for f, (before, after) in results.items():
        print("CHECK_OK" if args.check else "PATCHED" if before != after else "ALREADY_PATCHED", f.relative_to(root))
    print("NRG_XTOOL_GSA_HSC434_V4_READY: source-only; login not attempted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
