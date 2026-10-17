#!/usr/bin/env python3
"""V32: certificate facts and OCSP are independent in LC's native Diagnose.

Read the same canonical ZSigner observation already installed by
patch_lc_certificate_observation.py; never claim a good certificate solely
because its signed metadata can be decoded.
"""
from pathlib import Path
import sys

MARKER = "NRG_V32_JITLESS_OBSERVABILITY_V1"
TARGET = Path("LiveContainerSwiftUI/Views/Settings/LCJITLessDiagnoseView.swift")

def unique_replace(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise ValueError(f"V32 expected one exact upstream anchor, got {source.count(before)}: {before[:72]!r}")
    return source.replace(before, after, 1)

def patch(source: str) -> str:
    if MARKER in source:
        required = (
            "LCUtils.certificateFacts(withKeyData: data, password: password)",
            "certificateLocalParsed",
            "certificateValidationIssue",
            "offlineCertificateExpiration",
            "DispatchQueue.main.async",
            "certificateStatus = 2",
            "notAfter",
            "OCSP",
        )
        if source.count(MARKER) != 1 or any(t not in source for t in required):
            raise ValueError("Partial or duplicate V32 JIT-Less observation patch")
        return source

    source = unique_replace(source,
        '    @State var certTeamId : String?\n',
        '''    @State var certTeamId : String?
    // NRG_V32_JITLESS_OBSERVABILITY_V1: local parse vs online OCSP are distinct.
    @State private var certificateLocalParsed = false
    @State private var offlineCertificateExpiration: String? = nil
    @State private var certificateValidationIssue: String? = nil
''')
    source = unique_replace(source,
        '''                    HStack {
                        Text("lc.jitlessDiag.certLastUpdate".loc)''',
        '''                    if certificateDataFound && certificatePasswordFound {
                        HStack {
                            Text("PKCS#12 Parsing")
                            Spacer()
                            Text(certificateLocalParsed ? "lc.common.yes".loc : "lc.common.no".loc)
                                .foregroundStyle(certificateLocalParsed ? .green : .red)
                        }
                    }
                    HStack {
                        Text("lc.jitlessDiag.certLastUpdate".loc)''')
    source = unique_replace(source,
        '''                        HStack {
                            Text("lc.jitlessDiag.certificateValidateUntil".loc)''',
        '''                        if certificateStatus != 0, let reason = certificateValidationIssue {
                            HStack(alignment: .top) {
                                Text("OCSP Verification")
                                Spacer()
                                Text(reason)
                                    .multilineTextAlignment(.trailing)
                                    .foregroundStyle(.orange)
                            }
                        }
                        HStack {
                            Text("lc.jitlessDiag.certificateValidateUntil".loc)''')
    source = unique_replace(source,
        '''        certificateDataFound = LCUtils.certificateData() != nil
        certificatePasswordFound = LCSharedUtils.certificatePassword() != nil
        if let lastUpdateDate''',
        '''        certificateDataFound = LCUtils.certificateData() != nil
        certificatePasswordFound = LCSharedUtils.certificatePassword() != nil
        certificateLocalParsed = false
        certificateValidationIssue = nil
        offlineCertificateExpiration = nil
        certTeamId = nil
        // Offline X.509 facts come from LC's own ZSigner/InitSimple parser.
        // They are not proof of certificate revocation status.
        if let data = LCUtils.certificateData(),
           let password = LCSharedUtils.certificatePassword(),
           let facts = LCUtils.certificateFacts(withKeyData: data, password: password) {
            certificateLocalParsed = true
            certTeamId = facts["teamIdentifier"]
            offlineCertificateExpiration = facts["notAfter"]
        }
        certificateValidateUntil = offlineCertificateExpiration
        if let lastUpdateDate''')
    source = unique_replace(source,
        '''    func validateCertificate() {
        certificateStatus = -1
        certificateValidateUntil = nil
        LCUtils.validateCertificate { status, date, ou, error in
            if let error {
                errorInfo = error.loc
                errorShow = true
                certificateStatus = 2
                return
            }
            certificateStatus = Int(status)
            if let date {
                let formatter1 = DateFormatter()
                formatter1.dateStyle = .short
                formatter1.timeStyle = .medium
                certificateValidateUntil = formatter1.string(from: date)
            }
            if let ou {
                certTeamId = ou
            }
        }
    }''',
        '''    func validateCertificate() {
        certificateStatus = -1
        certificateValidationIssue = nil
        // Do not clear offline X.509 facts while awaiting an OCSP network reply.
        certificateValidateUntil = offlineCertificateExpiration
        LCUtils.validateCertificate { status, date, ou, error in
            // URLSession's OCSP completion may be off the main queue.
            DispatchQueue.main.async {
                if let error {
                    certificateStatus = 2
                    certificateValidationIssue = Self.safeOCSPFailure(error)
                    return
                }
                certificateStatus = Int(status)
                if certificateStatus != 0 && certificateStatus != 1 {
                    certificateValidationIssue = "OCSP did not confirm certificate status."
                }
                if let date {
                    let formatter = DateFormatter()
                    formatter.dateStyle = .short
                    formatter.timeStyle = .medium
                    certificateValidateUntil = formatter.string(from: date)
                }
                if let ou, !ou.isEmpty { certTeamId = ou }
            }
        }
    }

    private static func safeOCSPFailure(_ nativeError: String) -> String {
        let value = nativeError.lowercased()
        if value.contains("password") || value.contains("initialize certificate") {
            return "PKCS#12 could not be decoded; check stored certificate and password."
        }
        if value.contains("issuer") { return "Certificate issuer could not be verified." }
        if value.contains("aia") || value.contains("ocsp uri") {
            return "Certificate has no usable Apple OCSP endpoint."
        }
        if value.contains("decode ocsp") { return "Apple OCSP response could not be decoded." }
        if value.contains("invalid response") || value.contains("no data") {
            return "OCSP server response was invalid or empty."
        }
        return "Apple OCSP validation failed or the service was unreachable."
    }''')
    return source

def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v32_jitless_diagnosis.py <pinned-LiveContainer-root>")
    file = Path(sys.argv[1]) / TARGET
    before = file.read_text(encoding="utf-8")
    after = patch(before)
    if after != before:
        file.write_text(after, encoding="utf-8")
        print("[PATCH] V32 local certificate facts vs OCSP diagnosis separated")
    else:
        print("[PASS] V32 JIT-Less diagnosis already patched")

if __name__ == "__main__":
    main()
