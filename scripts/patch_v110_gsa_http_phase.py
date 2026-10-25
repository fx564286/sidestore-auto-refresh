#!/usr/bin/env python3
"""Expose GrandSlam HTTP error phase through the existing safe status logger."""
from pathlib import Path
import sys

FILE=Path("Dependencies/SideSign/Sources/DeveloperPortal/Authentication.swift")
MARK="SCARLET_V110_GSA_HTTP_PHASE"

def one(s,a,b):
    if s.count(a)!=1: raise ValueError(f"V110 expected one anchor, found {s.count(a)}")
    return s.replace(a,b,1)

def transform(s):
    if MARK in s:
        audit(s)
        return s
    for token in ("NRG_GSA_HTTP_STATUS_V2","SCARLET_V98_GSA_PHASE_TRACE"):
        if token not in s:raise ValueError("V110 requires "+token)
    s=one(s,
        'request: request, operation: requestParameters["o"] as? String ?? "unknown")',
        'request: request, operation: requestParameters["o"] as? String ?? "unknown",\n                anisetteClientInfo: anisetteData.clientInfo)')
    s=one(s,
        'request: URLRequest, operation: String\n    ) async throws -> (Data, URLResponse) {',
        'request: URLRequest, operation: String, anisetteClientInfo: String\n    ) async throws -> (Data, URLResponse) {')
    old='''                throw ServerError.underlyingError(
                    code: status, message: "NRG_GSA_HTTP_\\(status)")'''
    new='''                // SCARLET_V110_GSA_HTTP_PHASE: status and family only.
                let sentInfo = request.value(forHTTPHeaderField: "X-MMe-Client-Info") ?? ""
                let sourceFamily: String = anisetteClientInfo.contains("<Android;") ? "android"
                    : anisetteClientInfo.contains("<Windows;") ? "windows"
                    : anisetteClientInfo.contains("<Mac") ? "mac" : "other"
                let sentFamily: String = sentInfo.contains("<Android;") ? "android"
                    : sentInfo.contains("<Windows;") ? "windows"
                    : sentInfo.contains("<Mac") ? "mac" : "other"
                nrgLogSafeAuthPhase(operation: safeOperation, httpStatus: status,
                                    appleCode: 0, anisetteFamily: sourceFamily,
                                    sentFamily: sentFamily)
''' + old
    s=one(s,old,new)
    audit(s)
    return s

def audit(s):
    for item in (MARK,"anisetteClientInfo: anisetteData.clientInfo",
        "nrgLogSafeAuthPhase(operation: safeOperation, httpStatus: status",
        "if isInit && (status == 502 || status == 503 || status == 504)"):
        if item not in s:raise ValueError("V110 safe phase marker missing: "+item)

def apply(root):
    p=root/FILE
    if not p.is_file() or p.is_symlink():raise ValueError("V110 auth source absent")
    before=p.read_text()
    after=transform(before)
    if transform(after)!=after:raise ValueError("V110 non-idempotent")
    if before!=after:p.write_text(after)
    print("[PASS] GSA HTTP error phase safe status logger")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: <EmbeddedSideStore>")
    apply(Path(sys.argv[1]))
