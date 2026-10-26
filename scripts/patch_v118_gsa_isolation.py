#!/usr/bin/env python3
"""V118: isolate one Apple authentication transaction in a single URLSession.

Preserves Anisette, SRP, OTP and device identity. No credential retries, no ADI
reset, no removal or signout. Strictly observational compatibility experiment.
"""
from pathlib import Path
import argparse

MARKER = 'SCARLET_V118_TRANSACTION_SESSION'
REL = Path('Sources/DeveloperPortal/Authentication.swift')
REQUIRED = ('NRG_GSA_HTTP_STATUS_V2', 'NRG_GSA_RECOVERY_V1',
            'SCARLET_V116_SIDEINSTALLER_PARITY', 'NRG_GSA_CLIENT_IDENTITY_V3')
IMPORT = 'import GSACryptoKit\n'
ENTRY_ANCHOR = '        let sanitizedAppleID = unsanitizedAppleID.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()\n'
HEADERS = '        headers.forEach { request.setValue($1, forHTTPHeaderField: $0) }\n'
BEFORE = 'session.data(for:'
AFTER = '(ScarletV118AuthTransport.current ?? session).data(for:'
TASKLOCAL = '''// SCARLET_V118_TRANSACTION_SESSION: a task-local network session, not
// a process-wide variable or a new Apple authentication identity.
private enum ScarletV118AuthTransport {
    @TaskLocal static var current: URLSession? = nil
}

'''
ENTRY = '''        // SCARLET_V118_TRANSACTION_SESSION: isolate cookie/connection state
        // and retain it across the authentic server-driven 2FA flow.
        if ScarletV118AuthTransport.current == nil {
            let config = URLSessionConfiguration.ephemeral
            config.requestCachePolicy = .reloadIgnoringLocalCacheData
            config.urlCache = nil
            config.httpShouldSetCookies = true
            let isolated = URLSession(configuration: config)
            defer { isolated.invalidateAndCancel() }
            return try await ScarletV118AuthTransport.$current.withValue(isolated) {
                try await self.authenticate(appleID: unsanitizedAppleID,
                    password: password, anisetteData: anisetteData,
                    xcodeVersion: xcodeVersion, machinePassword: machinePassword,
                    accountRepairHandler: accountRepairHandler,
                    verificationHandler: verificationHandler)
            }
        }
'''
DIAG = '''        // SCARLET_V118_GSA_INTEGRITY: no identifiable data in diagnostics.
        let nrgFieldsComplete = [anisetteData.machineID,
            anisetteData.oneTimePassword, anisetteData.localUserID,
            anisetteData.routingInfo, anisetteData.deviceID]
            .allSatisfy { !$0.isEmpty }
        let nrgProfileCoherent = headers["X-MMe-Client-Info"] ==
            nrgGrandSlamClientInfo(anisetteData.clientInfo)
        let nrgClockClass: String = {
            let formatter = ISO8601DateFormatter()
            formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            let timestamp = formatter.date(from: anisetteData.clientTime)
                ?? ISO8601DateFormatter().date(from: anisetteData.clientTime)
            guard let timestamp else { return "unparseable" }
            let age = abs(timestamp.timeIntervalSinceNow)
            return age <= 300 ? "within5m" : (age <= 1800 ? "within30m" : "over30m")
        }()
        let rawPhase = requestParameters["o"] as? String ?? ""
        let nrgPhase = ["init", "complete", "apptokens"].contains(rawPhase)
            ? rawPhase : "other"
        print("[SCARLET_V118_GSA_INTEGRITY] phase=\\(nrgPhase) fields_complete=\\(nrgFieldsComplete) profile_coherent=\\(nrgProfileCoherent) time=\\(nrgClockClass) session=isolated")
'''
# Python raw string above has two backslashes for escaping through Python's
# triple quoted Swift snippet. The emitted Swift string uses single \(...).
def transform(src: str) -> str:
    if MARKER in src:
        if (src.count(MARKER) != 2 or src.count('SCARLET_V118_GSA_INTEGRITY') != 2
                or TASKLOCAL not in src or ENTRY not in src or DIAG not in src
                or src.count(AFTER) != 5 or BEFORE in src):
            raise ValueError('V118 partial or drifted installation')
        return src
    for token in REQUIRED:
        if token not in src:
            raise ValueError('V118 prerequisite absent: ' + token)
    for token, n in ((IMPORT, 1), (ENTRY_ANCHOR, 1), (HEADERS, 2), (BEFORE, 5)):
        if src.count(token) != n:
            raise ValueError('V118 source anchor drifted: ' + token[:40])
    out = src.replace(IMPORT, IMPORT + '\n' + TASKLOCAL, 1)
    out = out.replace(ENTRY_ANCHOR, ENTRY + ENTRY_ANCHOR, 1)
    out = out.replace(HEADERS, DIAG + HEADERS, 1)
    out = out.replace(BEFORE, AFTER)
    return out

def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('sidesign_root', type=Path)
    mode = cli.add_mutually_exclusive_group(required=True)
    mode.add_argument('--apply', action='store_true')
    mode.add_argument('--check', action='store_true')
    a = cli.parse_args()
    path = a.sidesign_root / REL
    before = path.read_text(encoding='utf-8')
    after = transform(before)
    if a.check:
        if after != before or MARKER not in before:
            cli.error('V118 patch is not installed')
        print('SCARLET_V118_SESSION_CHECK_OK')
    elif before != after:
        path.write_text(after, encoding='utf-8')
        print('SCARLET_V118_SESSION_APPLIED')
    else:
        print('SCARLET_V118_SESSION_ALREADY_APPLIED')

if __name__ == '__main__':
    main()
