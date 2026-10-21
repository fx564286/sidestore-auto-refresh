#!/usr/bin/env python3
"""Add strictly metadata-only GrandSlam phase logging to isolated xtool 1.22.2.

Source-only; no account operations, passwords, tokens, HTTP bodies, device IDs,
certificates, signing, revocation, or installation. Requires NRG xtool auth V1.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess

PIN = "65bf3cc5a1240fea53ac0748d29a01878222a6ce"
REL = Path("Sources/XKit/GrandSlam/GrandSlamClient.swift")
MARKER = "NRG_XTOOL_AUTH_TRACE_V2"

OLD = """        let deviceInfo = try deviceInfoProvider.fetch()

        let anisetteData = try await anisetteDataProvider.fetchAnisetteData()
        let url = try await lookupManager.fetchURL(forEndpoint: R.endpoint)

        let method = request.method(deviceInfo: deviceInfo, anisetteData: anisetteData)"""

NEW = """        // NRG_XTOOL_AUTH_TRACE_V2: opt-in phase only; never include account or request data.
        let tracing = DeviceInfo.nrgSideStoreAuth
            && ProcessInfo.processInfo.environment["NRG_XTOOL_AUTH_TRACE"] == "1"
        let phase: String
        switch request {
        case is GrandSlamAuthInitRequest: phase = "init"
        case is GrandSlamAuthCompleteRequest: phase = "complete"
        case is GrandSlamAppTokensRequest: phase = "apptokens"
        case is GrandSlamValidateRequest: phase = "2fa_validate"
        case is GrandSlamTrustedDeviceRequest: phase = "2fa_trusted"
        default: phase = "other"
        }

        let deviceInfo = try deviceInfoProvider.fetch()
        let anisetteData: AnisetteData
        do {
            anisetteData = try await anisetteDataProvider.fetchAnisetteData()
        } catch {
            if tracing { print("[NRG_AUTH_TRACE] phase=anisette result=failed") }
            throw error
        }
        let url: URL
        do {
            url = try await lookupManager.fetchURL(forEndpoint: R.endpoint)
        } catch {
            if tracing { print("[NRG_AUTH_TRACE] phase=lookup result=failed") }
            throw error
        }

        let method = request.method(deviceInfo: deviceInfo, anisetteData: anisetteData)"""

OLD_RESPONSE = """        let resp = try await httpClient.withEphemeralClient {
            try await $0.makeRequest(httpRequest, body: body)
        }
        return try R.Decoder.decode(data: resp.body)"""

NEW_RESPONSE = """        do {
            let resp = try await httpClient.withEphemeralClient {
                try await $0.makeRequest(httpRequest, body: body)
            }
            do {
                let decoded = try R.Decoder.decode(data: resp.body)
                if tracing {
                    print("[NRG_AUTH_TRACE] phase=\\(phase) http=\\(resp.response.status.code) result=ok")
                }
                return decoded
            } catch let error as GrandSlamOperationError {
                if tracing {
                    print("[NRG_AUTH_TRACE] phase=\\(phase) http=\\(resp.response.status.code) gsa_code=\\(error.code)")
                }
                throw error
            } catch {
                if tracing {
                    print("[NRG_AUTH_TRACE] phase=\\(phase) http=\\(resp.response.status.code) result=decode_failed")
                }
                throw error
            }
        } catch let error as HTTPResponseError {
            if tracing {
                print("[NRG_AUTH_TRACE] phase=\\(phase) http=\\(error.status.code) result=http_failed")
            }
            throw error
        } catch {
            if tracing {
                print("[NRG_AUTH_TRACE] phase=\\(phase) result=transport_or_other_error")
            }
            throw error
        }"""


def transform(text: str) -> str:
    if MARKER in text:
        if text.count(MARKER) != 1 or NEW_RESPONSE not in text or NEW not in text:
            raise ValueError("Partial or drifted V2 trace patch")
        return text
    if "NRG_XTOOL_SIDESTORE_AUTH_V1" not in text:
        raise ValueError("V1 isolated auth patch prerequisite missing")
    if text.count(OLD) != 1 or text.count(OLD_RESPONSE) != 1:
        raise ValueError("Expected exactly one source anchor for trace patch")
    return text.replace(OLD, NEW, 1).replace(OLD_RESPONSE, NEW_RESPONSE, 1)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("xtool_source", type=Path)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = p.parse_args()
    root = args.xtool_source.resolve()
    if not (root / ".git").is_dir():
        p.error("Refusing to patch non-repository directory")
    sha = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if sha != PIN:
        p.error("xtool commit mismatch; only tag 1.22.2 supported")
    target = root / REL
    before = target.read_text(encoding="utf-8")
    after = transform(before)
    if args.check and (before != after or MARKER not in before):
        p.error("Trace patch missing")
    if args.apply and before != after:
        target.write_text(after, encoding="utf-8")
    print("NRG_AUTH_TRACE_V2_CHECK_OK" if args.check else "NRG_AUTH_TRACE_V2_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
