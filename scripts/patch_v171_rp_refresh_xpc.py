#!/usr/bin/env python3
"""V171: preserve VERIFIED RemotePairing typed causes at final refresh XPC.

Applied AFTER patch_combined_service_startup.py, whose generated SideStoreClient
already owns the bounded CombinedFailure wire format. Do not add a second
wire codec. Preserve run correlation, do not include raw errors, and reject
untyped or unrelated POSIX reset errors.
"""
from pathlib import Path
import sys

FILE=Path("SideStoreSupport/SideStoreClient.swift")
MARK="SCARLET_V171_RP_FAILURE_XPC"
OLD='reportRefreshResult(CombinedFailure.capture(error, operation: "refresh", stage: .command, id: runID).encodedString, runID: runID, server: server)'
NEW='reportRefreshResult(CombinedFailure.capture(v171VerifiedRPReset(error), operation: "refresh", stage: .command, id: runID).encodedString, runID: runID, server: server)'
ANCHOR='    @available(iOS 17.0, *)\n    extension SideStoreClient {'
HELPER=r'''    // SCARLET_V171_RP_FAILURE_XPC: only a V170 local typed RP error can
    // produce this fixed category. The legacy generic NSError cannot.
    private func v171VerifiedRPReset(_ error: Error) -> Error {
        var current = error as NSError
        for _ in 0..<6 {
            if current.domain == NSPOSIXErrorDomain && current.code == 54 &&
               current.userInfo["LCStructuredFailureStageV1"] as? String == "pairing" &&
               current.userInfo["LCStructuredFailureCauseV1"] as? String == "remotePairingHandshakeReset" {
                return NSError(domain: NSPOSIXErrorDomain, code: 54, userInfo: [
                    "LCStructuredFailureStageV1": "pairing",
                    "LCStructuredFailureCauseV1": "remotePairingHandshakeReset"
                ])
            }
            guard let next = current.userInfo[NSUnderlyingErrorKey] as? NSError else { break }
            current = next
        }
        return error
    }

'''

def patch(s: str) -> str:
    if MARK in s:
        if s.count(MARK)!=1 or NEW not in s:raise ValueError("V171 partial RP bridge")
        return s
    if "LC_REFRESH_RESULT_XPC_V1" not in s or "reportStructuredRefreshFailure" not in s:
        raise ValueError("final combined refresh bridge not yet installed")
    if s.count(ANCHOR)!=1 or s.count(OLD)!=1:
        raise ValueError("V171 pinned final error adapter anchor drift")
    return s.replace(ANCHOR,HELPER+ANCHOR,1).replace(OLD,NEW,1)

def main(root: Path):
    p=root/FILE
    if not p.is_file() or p.is_symlink():raise ValueError("pinned host SideStoreClient missing")
    before=p.read_text(encoding="utf-8");after=patch(before)
    if patch(after)!=after:raise ValueError("V171 patch not idempotent")
    if before!=after:p.write_text(after,encoding="utf-8")
    print("[PASS] V171 typed RP reset propagated via original CombinedFailure codec")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v171_rp_refresh_xpc.py <LiveContainer>")
    main(Path(sys.argv[1]))
