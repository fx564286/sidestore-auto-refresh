#!/usr/bin/env python3
"""V164: repair RemotePairing retry selection after TCP-reachable TLS reset.

No pairing record, certificate, provisioning, VPN preference or app container is
created/rewritten. Recover a stale port on the current VPN peer *before* trying
an mDNS Wi-Fi host; allow one delayed same-endpoint retry for transient RST.
All retries are bounded; unrelated or authentication errors are not hidden.
"""
from pathlib import Path
import sys

SOURCE=Path('SideStore/Core/DeviceApi/MinimuxerWrapper.swift')
MARK='SCARLET_V164_TRANSPORT_RESYNC'

NEW_RETRY=r'''// SCARLET_V164_TRANSPORT_RESYNC: V140 only attempted the Bonjour host.
// On LocalDevVPN a service announcement often contains the phone's Wi-Fi
// address even though the actual RPPairing route is the uTun peer. Try the
// discovered *port on the existing peer* before switching hosts. A reachable
// TCP socket does not establish RemotePairing TLS authentication.
private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {
    do {
        return try await operation()
    } catch {
        let firstError = error
        let gateway = minimuxer.gateway
        guard gateway.pairingFileType == .rppairing else { throw firstError }
        let message = String(describing: firstError).lowercased()
        // Never overwrite pairing data or turn an explicit authentication
        // failure into a network retry; user approval is required to re-pair.
        if message.contains("invalidpairing") || message.contains("invalid pairing") ||
           message.contains("pairverifyfailed") || message.contains("pair verify failed") ||
           message.contains("authentication failed") {
            NSLog("[SCARLET_V164_TRANSPORT_RESYNC] stage=auth decision=manual_repair record=preserved")
            throw firstError
        }
        guard let initialHost = gateway.deviceEndpointIp, !initialHost.isEmpty else {
            throw firstError
        }
        let initialPort = gateway.getPort(for: .rppairing)
        // SCARLET_V142_NETWORK_GENERATION_GUARD: preserve route ownership
        // during asynchronous discovery and on the last restoration.
        let now = Date()
        guard now.timeIntervalSince(lastV140BonjourRetryTime) >= 5 else {
            NSLog("[SCARLET_V164_TRANSPORT_RESYNC] stage=retry decision=throttled")
            throw firstError
        }
        lastV140BonjourRetryTime = now

        let discovered = await resolveV140RemotePairingEndpoint()
        // The asynchronous Bonjour lookup must never restore or redirect an
        // endpoint replaced by the VPN/network observer in the meantime.
        guard gateway.deviceEndpointIp == initialHost &&
              gateway.getPort(for: .rppairing) == initialPort else {
            NSLog("[SCARLET_V164_TRANSPORT_RESYNC] stage=route decision=changed_skip")
            throw firstError
        }

        var candidates: [(host: String, port: UInt16, mode: String)] = []
        if let discovered, discovered.port != initialPort {
            candidates.append((initialHost, discovered.port, "vpn_peer_discovered_port"))
        }
        // iOS can reset a valid TCP connection while advertising the same
        // endpoint. Allow ONE delayed same-endpoint handshake retry only.
        let transientReset = message.contains("connection reset") ||
            message.contains("connectionreset") || message.contains("operation timeout") ||
            message.contains("timed out")
        if transientReset && (discovered == nil || discovered?.port == initialPort) {
            candidates.append((initialHost, initialPort, "transient_same_endpoint"))
        }
        if let discovered,
           (discovered.host != initialHost || discovered.port != initialPort) {
            candidates.append((discovered.host, discovered.port, "bonjour_service_endpoint"))
        }
        guard !candidates.isEmpty else {
            NSLog("[SCARLET_V164_TRANSPORT_RESYNC] stage=discovery decision=no_candidate")
            throw firstError
        }

        var expectedHost = initialHost
        var expectedPort = initialPort
        var lastError: Error = firstError
        for candidate in candidates.prefix(3) {
            guard gateway.deviceEndpointIp == expectedHost &&
                  gateway.getPort(for: .rppairing) == expectedPort else {
                NSLog("[SCARLET_V164_TRANSPORT_RESYNC] stage=route decision=handoff_skip")
                throw firstError
            }
            if candidate.host != expectedHost { gateway.setDeviceEndpointIp(candidate.host) }
            if candidate.port != expectedPort { gateway.setPort(candidate.port, for: .rppairing) }
            expectedHost = candidate.host
            expectedPort = candidate.port
            if candidate.mode == "transient_same_endpoint" {
                try? await Task.sleep(nanoseconds: 250_000_000)
            }
            do {
                let result = try await operation()
                remotePairingPortCache = candidate.port
                NSLog("[SCARLET_V164_TRANSPORT_RESYNC] stage=handshake decision=success mode=%@", candidate.mode)
                return result
            } catch {
                lastError = error
                NSLog("[SCARLET_V164_TRANSPORT_RESYNC] stage=handshake decision=failed mode=%@", candidate.mode)
                // Do not try other network targets after a definite pairing
                // identity rejection. No amount of TCP retries can re-pair.
                let reason = String(describing: error).lowercased()
                if reason.contains("invalidpairing") || reason.contains("pairverifyfailed") ||
                   reason.contains("invalid pairing") {
                    break
                }
            }
        }
        // Restore only if the route is *still* the endpoint we installed;
        // never resurrect the stale VPN peer after the network disappeared.
        if gateway.deviceEndpointIp == expectedHost &&
           gateway.getPort(for: .rppairing) == expectedPort {
            if expectedHost != initialHost { gateway.setDeviceEndpointIp(initialHost) }
            if expectedPort != initialPort { gateway.setPort(initialPort, for: .rppairing) }
            remotePairingPortCache = initialPort
            NSLog("[SCARLET_V164_TRANSPORT_RESYNC] stage=recovery decision=all_failed route=restored record=preserved")
        } else {
            NSLog("[SCARLET_V164_TRANSPORT_RESYNC] stage=recovery decision=route_changed_no_restore")
        }
        throw lastError
    }
}
'''


def patch_source(source: str) -> str:
    if '// '+MARK+':' in source:
        if source.count('// '+MARK+':')!=1 or source.count('stage=recovery decision=all_failed')!=1:
            raise ValueError('V164 partial or duplicated recovery logic')
        return source
    for required in ('SCARLET_V140_BONJOUR_ENDPOINT_RETRY',
                     'SCARLET_V142_NETWORK_GENERATION_GUARD',
                     'private func resolveV140RemotePairingEndpoint()',
                     'private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {'):
        if required not in source:
            raise ValueError('V164 requires V142 source: '+required)
    start=source.index('private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {')
    end=source.index('\npublic var minimuxerStatusPublisher:',start)
    if 'route_changed_not_restored' not in source[start:end]:
        raise ValueError('V164 stale V142 anchor: handoff guard missing')
    return source[:start]+NEW_RETRY+source[end:]


def apply(root: Path):
    p=root/SOURCE
    if not p.is_file() or p.is_symlink():
        raise ValueError('V164 upstream SideStore not found')
    old=p.read_text(encoding='utf-8')
    new=patch_source(old)
    if patch_source(new)!=new:
        raise ValueError('V164 not idempotent')
    if new!=old:
        p.write_text(new,encoding='utf-8')
    print('[PASS] V164 bounded RP retry: current peer/discovered port, transient reset, Bonjour host, safe rollback')

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('usage: patch_v164_rp_handshake_recovery.py <EmbeddedSideStore>')
    apply(Path(sys.argv[1]))
