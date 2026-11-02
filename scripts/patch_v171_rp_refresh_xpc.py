#!/usr/bin/env python3
"""V171: preserve verified RP resets through LiveProcess refresh XPC.

SideStoreSupport previously sent only error.localizedDescription, discarding
structured failure. Rebuild an allowlisted plist ONLY if the NSError chain
contains V170's exact local typed marker; no pairing data is transmitted.
"""
from pathlib import Path
import sys
PATH=Path("SideStoreSupport/SideStoreClient.swift")
MARK="SCARLET_V171_RP_FAILURE_XPC"
ANCHOR="@available(iOS 17.0, *)\n@objc extension SideStoreClient {"
OLD='reportRefreshResult(error.localizedDescription, runID: refreshRunID, server: server)'
NEW='reportRefreshResult(v171TypedRPRefreshFailure(error, runID: refreshRunID) ?? error.localizedDescription, runID: refreshRunID, server: server)'
HELPER=r'''// SCARLET_V171_RP_FAILURE_XPC: only known typed V170 RP resets cross XPC.
// No arbitrary NSError text or userInfo is forwarded to the host.
private func v171TypedRPRefreshFailure(_ error: Error, runID: String?) -> String? {
    guard let runID, UUID(uuidString: runID) != nil else { return nil }
    var native = error as NSError
    var typedRPReset = false
    for _ in 0..<6 {
        if native.domain == NSPOSIXErrorDomain && native.code == 54 &&
           native.userInfo["LCStructuredFailureCauseV1"] as? String == "remotePairingHandshakeReset" &&
           native.userInfo["LCStructuredFailureStageV1"] as? String == "pairing" {
            typedRPReset = true
            break
        }
        guard let nested = native.userInfo[NSUnderlyingErrorKey] as? NSError else { break }
        native = nested
    }
    guard typedRPReset else { return nil }
    let wire: [String: Any] = [
        "version": 1, "operation": "refresh", "stage": "pairing",
        "code": "failed", "correlationID": runID,
        "underlyingDomain": "NSPOSIXErrorDomain", "underlyingCode": 54,
        "safeCause": "remotePairingHandshakeReset", "retryable": false
    ]
    guard let data = try? PropertyListSerialization.data(
        fromPropertyList: wire, format: .binary, options: 0),
        data.count <= 4096 else { return nil }
    return "LCFAILURE1:" + data.base64EncodedString()
}

'''

def patch(s: str) -> str:
    if MARK in s:
        if s.count(MARK)!=1 or NEW not in s:raise ValueError("V171 partial RP failure bridge")
        return s
    if "LC_REFRESH_RESULT_XPC_V1" not in s:raise ValueError("V21 refresh bridge prerequisite missing")
    if s.count(OLD)!=1 or s.count(ANCHOR)!=1:raise ValueError("V171 refresh bridge anchor drift")
    return s.replace(ANCHOR,HELPER+ANCHOR,1).replace(OLD,NEW,1)

def main(root: Path):
    p=root/PATH
    if not p.is_file() or p.is_symlink():raise ValueError("expected pinned SideStoreSupport source")
    s=p.read_text(encoding="utf-8");t=patch(s)
    if patch(t)!=t:raise ValueError("V171 not idempotent")
    if s!=t:p.write_text(t,encoding="utf-8")
    print("[PASS] V171 typed RP failure retained across refresh XPC; no raw errors transmitted")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v171_rp_refresh_xpc.py <LiveContainer>")
    main(Path(sys.argv[1]))
