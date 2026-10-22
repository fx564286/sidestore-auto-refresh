#!/usr/bin/env python3
"""V69: recover *transient* signed-host UDID fetch failures before resigning.

The 2026-10-22 iPhone log showed valid certificate + 4 profiles, then an
unreachable 10.7.0.1 RemotePairing endpoint and fetchUDID() nil during
ResignAppOperation. This patch retries *only* the existing trusted fetchUDID()
for a bounded period. It NEVER fabricates a device ID or ignores pairing,
certificates, provisioning profiles, cancellation, or entitlement validation.
"""
from pathlib import Path
import sys

TARGET = Path('SideStore/Core/Operations/PipelineOperations/ResignAppOperation.swift')
MARKER = 'NRG_V69_SIGNING_UDID_RETRY'
OLD = '''        if targetAppBundle.isAltStoreApp {
            let udid: String
            do {
                await CellularRefreshManager.shared.turnOffDataIfNeeded()
                guard let fetchedUdid = try await fetchUDID() else { throw OperationError.unknownUDID }
                udid = fetchedUdid
            } catch {
                await CellularRefreshManager.shared.turnOnDataIfNeeded()
                throw error
            }
'''
NEW = '''        if targetAppBundle.isAltStoreApp {
            let udid: String
            do {
                await CellularRefreshManager.shared.turnOffDataIfNeeded()
                // NRG_V69_SIGNING_UDID_RETRY — transient VPN/RemotePairing
                // flaps must not abort an otherwise provisioned self-sign.
                // Never use a guessed, stored or other-device UDID.
                var observedUDID: String? = nil
                for attempt in 1...4 {
                    try Task.checkCancellation()
                    do {
                        observedUDID = try await fetchUDID()
                    } catch is CancellationError {
                        throw CancellationError()
                    } catch {
                        // Only a bounded retry; the last typed source error
                        // propagates unchanged instead of being relabelled.
                        if attempt == 4 { throw error }
                        self.debugLog("[NRG_V69_SIGNING_UDID] fetch_failed attempt=\\(attempt) retry=true")
                    }
                    if let candidate = observedUDID, !candidate.isEmpty { break }
                    if attempt < 4 {
                        self.debugLog("[NRG_V69_SIGNING_UDID] unavailable attempt=\\(attempt) retry=true")
                        try await Task.sleep(nanoseconds: UInt64(attempt) * 1_000_000_000)
                    }
                }
                guard let verifiedUDID = observedUDID, !verifiedUDID.isEmpty else {
                    self.debugLog("[NRG_V69_SIGNING_UDID] result=unavailable signing_skipped=true")
                    throw OperationError.unknownUDID
                }
                self.debugLog("[NRG_V69_SIGNING_UDID] result=verified signing_allowed=true")
                udid = verifiedUDID
            } catch {
                await CellularRefreshManager.shared.turnOnDataIfNeeded()
                throw error
            }
'''


def patch(text: str) -> str:
    if MARKER in text:
        if text.count(MARKER) != 1 or OLD in text:
            raise ValueError('Partial V69 UDID retry patch')
        return text
    if text.count(OLD) != 1:
        raise ValueError(f'Expected one pinned resign UDID block; found {text.count(OLD)}')
    return text.replace(OLD, NEW, 1)


def main(root: Path) -> None:
    dest = root / TARGET
    dest.write_text(patch(dest.read_text(encoding='utf-8')), encoding='utf-8')
    print('[PASS] V69: bounded verified UDID retry; native code signing unchanged')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: patch_v69_signing_udid_retry.py EMBEDDED_SIDESTORE_ROOT')
    main(Path(sys.argv[1]))
