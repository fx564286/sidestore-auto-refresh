#!/usr/bin/env python3
"""V5: bounded HTTP 503 recovery after one SideInstaller-style hsc434 resync.

Only in isolated opt-in xtool 1.22.2 and exclusively during an init replay
following hsc=434. Preserve credentials, Anisette identity, certificates,
bundle IDs, and existing NRG. Do NOT retry complete, apptokens, or 2FA.
No authentication is attempted by this source-only patcher.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess

PIN = "65bf3cc5a1240fea53ac0748d29a01878222a6ce"
TARGET = Path("Sources/XKit/GrandSlam/GrandSlamClient.swift")
MARKER = "NRG_XTOOL_GSA_503_V5"
OLD = """                    let refreshed = try await adi.nrgResync(sim: sim)
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
                    return decoded"""
NEW = """                    // NRG_XTOOL_GSA_503_V5: distinguish remote v3 resync success
                    // from Apple's HTTP 503 on the following GSA replay.
                    let refreshed: AnisetteData
                    do {
                        refreshed = try await adi.nrgResync(sim: sim)
                        if tracing {
                            print("[NRG_AUTH_TRACE] phase=init anisette_resync=completed")
                        }
                    } catch let resyncHTTP as HTTPResponseError {
                        if tracing {
                            print("[NRG_AUTH_TRACE] phase=anisette_resync http=\\(resyncHTTP.status.code) result=failed")
                        }
                        throw resyncHTTP
                    } catch {
                        if tracing {
                            print("[NRG_AUTH_TRACE] phase=anisette_resync result=failed")
                        }
                        throw error
                    }
                    let retryMethod = request.method(
                        deviceInfo: deviceInfo, anisetteData: refreshed)
                    let retryBody: Data? = switch retryMethod {
                    case .get: nil
                    case .post(let data):
                        try PropertyListSerialization.data(
                            fromPropertyList: data, format: .xml, options: 0)
                    }
                    // A fresh connection for every attempt. ONLY retry
                    // Apple's 503 for this init step, with capped 2s/5s
                    // backoff. Do not regenerate or reprovision the identity.
                    for index in 0..<3 {
                        do {
                            let retried = try await httpClient.withEphemeralClient {
                                try await $0.makeRequest(httpRequest, body: retryBody)
                            }
                            let decoded = try R.Decoder.decode(data: retried.body)
                            if tracing {
                                print("[NRG_AUTH_TRACE] phase=init apple_replay=ok attempt=\\(index + 1)")
                            }
                            return decoded
                        } catch let replayHTTP as HTTPResponseError {
                            guard replayHTTP.status.code == 503 && index < 2 else {
                                if tracing {
                                    print("[NRG_AUTH_TRACE] phase=init apple_replay_http=\\(replayHTTP.status.code) retry=exhausted")
                                }
                                throw replayHTTP
                            }
                            if tracing {
                                print("[NRG_AUTH_TRACE] phase=init apple_replay_http=503 retry=\\(index + 2)")
                            }
                            let delay: UInt64 = index == 0 ? 2_000_000_000 : 5_000_000_000
                            try await Task.sleep(nanoseconds: delay)
                        }
                    }
                    throw NRGAnisetteResyncError.unsupported"""


def transform(text: str) -> str:
    if MARKER in text:
        if text.count(MARKER) != 1 or text.count(NEW) != 1:
            raise ValueError("V5 duplicate or partial patch; refusing source drift")
        return text
    if "NRG_XTOOL_GSA_HSC434_V4" not in text:
        raise ValueError("Missing V4 hsc434 prerequisite")
    if text.count(OLD) != 1:
        raise ValueError("V4 expected source anchor count is not 1")
    return text.replace(OLD, NEW, 1)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("xtool_checkout", type=Path)
    a = p.add_mutually_exclusive_group(required=True)
    a.add_argument("--apply", action="store_true")
    a.add_argument("--check", action="store_true")
    args = p.parse_args()
    root = args.xtool_checkout.resolve()
    if not (root / ".git").is_dir():
        p.error("Not an isolated git clone")
    sha = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if sha != PIN:
        p.error("Only pinned xtool 1.22.2 is supported")
    f = root / TARGET
    before = f.read_text(encoding="utf-8")
    after = transform(before)
    if args.check and (before != after or MARKER not in before):
        p.error("V5 missing or partial")
    if args.apply and before != after:
        f.write_text(after, encoding="utf-8")
    print("NRG_XTOOL_GSA_503_V5_CHECK_OK" if args.check else "NRG_XTOOL_GSA_503_V5_APPLIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
