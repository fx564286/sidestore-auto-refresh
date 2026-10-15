#!/usr/bin/env python3
"""Source-only, idempotent fix for the pinned SideSign GrandSlam HTTP boundary.

Does not alter app identities, credentials, Anisette headers, OTP sessions or the Apple account.
Apply to a throwaway checkout of a maintained SideSign revision for a reviewed build.
"""
from __future__ import annotations

import argparse
import pathlib
import sys

MARKER = "NRG_GSA_HTTP_STATUS_V2"
AUTH_RELATIVE = pathlib.Path("Sources/DeveloperPortal/Authentication.swift")

OLD_CALL = '''        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            debugLog("[SideSign] sendAuthenticationRequest network error: \\(error)")
            throw error
        }

        let httpResponse = response as? HTTPURLResponse
        let statusCode = httpResponse?.statusCode ?? 0
'''

NEW_CALL = '''        // NRG_GSA_HTTP_STATUS_V2: classify HTTP status BEFORE interpreting plist/JSON.
        // Only SRP init is eligible for bounded retries; never replay SRP complete,
        // apptokens, verification codes, or any other authenticated transition.
        let (data, response): (Data, URLResponse)
        do {
            (data, response) = try await sendGSAHTTPWithInitRetry(
                request: request, operation: requestParameters["o"] as? String ?? "unknown")
        } catch {
            debugLog("[SideSign] GSA request failed; no HTTP payload logged")
            throw error
        }

        let httpResponse = response as? HTTPURLResponse
        let statusCode = httpResponse?.statusCode ?? 0
'''

# Placed in the same DeveloperPortal extension, near the GSA dispatcher.
HELPER = '''    // NRG_GSA_HTTP_STATUS_V2
    // A 503 can be genuinely server-side; retry cannot guarantee login success.
    // No body, cookies, account identifiers, headers or tokens enter error text.
    private func sendGSAHTTPWithInitRetry(
        request: URLRequest, operation: String
    ) async throws -> (Data, URLResponse) {
        let isInit = operation == "init"
        let attempts = isInit ? 3 : 1
        for index in 0..<attempts {
            try Task.checkCancellation()
            let (body, response) = try await session.data(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw ServerError.badServerResponse(
                    reason: "GSA response did not contain an HTTP status", jsonPayload: "")
            }
            let status = http.statusCode
            // NRG_GSA_STEP_TRACE_V4: emit only whitelisted operation and HTTP
            // status, no headers, credentials, request body or server response.
            let safeOperation = ["init", "complete", "apptokens"].contains(operation) ? operation : "other"
            debugLog("[NRG_GSA_STEP] operation=\(safeOperation) status=\(status) attempt=\(index + 1)")
            // 429 is NOT automatically retried; this protects rate limits.
            // 401/403/409/422 and other failures are also not replayed.
            if status == 429 || status >= 500 {
                if isInit && (status == 502 || status == 503 || status == 504)
                    && index + 1 < attempts {
                    // Fixed low upper bound; do not retry a password/OTP submission.
                    let delay: UInt64 = index == 0 ? 1_000_000_000 : 2_000_000_000
                    try await Task.sleep(nanoseconds: delay)
                    continue
                }
                throw ServerError.underlyingError(
                    code: status, message: "NRG_GSA_HTTP_\\(status)")
            }
            return (body, response)
        }
        throw ServerError.badServerResponse(
            reason: "GSA initial request retry budget exhausted", jsonPayload: "")
    }

'''


def transform(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 2 or "sendGSAHTTPWithInitRetry(" not in source:
            raise ValueError("Partial NRG V2 patch found; refusing ambiguous repair")
        return source
    if source.count(OLD_CALL) != 1:
        raise ValueError("Expected exactly one unmodified sendAuthenticationRequest HTTP call; check SideSign pin")
    anchor = "    private struct FetchedAuthToken {"
    if source.count(anchor) != 1:
        raise ValueError("Unable to locate GrandSlam dispatcher insertion point")
    out = source.replace(OLD_CALL, NEW_CALL, 1).replace(anchor, HELPER + anchor, 1)
    assert out.count(MARKER) == 2
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apply or verify NRG GSA HTTP classification/retry patch")
    parser.add_argument("sidesign_root", type=pathlib.Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Verify that this exact patch is applied")
    mode.add_argument("--apply", action="store_true", help="Patch the specified source checkout")
    args = parser.parse_args(argv)
    auth = args.sidesign_root / AUTH_RELATIVE
    if not auth.is_file():
        parser.error(f"No SideSign Authentication.swift: {auth}")
    old = auth.read_text(encoding="utf-8")
    if args.check:
        if old.count(MARKER) != 2:
            parser.error("NRG V2 GSA patch is not present or is partial")
        if transform(old) != old:
            parser.error("GSA patch verification is not idempotent")
        print("GSA_V2_CHECK_OK", auth)
        return 0
    new = transform(old)
    if new != old:
        auth.write_text(new, encoding="utf-8")
        print("GSA_V2_PATCH_APPLIED", auth)
    else:
        print("GSA_V2_ALREADY_APPLIED", auth)
    return 0


if __name__ == "__main__":
    sys.exit(main())
