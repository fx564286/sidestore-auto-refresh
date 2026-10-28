#!/usr/bin/env python3
"""V140: repair reset loop when Bonjour finds a new RemotePairing *host*.

Preserves paired records, keys, certificates, and user network preferences.
The existing V138 route only retries when a PORT changes; on V139 the
host changed from 10.7.0.1 to 10.204.186.52 but both used port 49152.
Retry exactly once with the discovered endpoint and roll back if unverified.
"""
from pathlib import Path
import sys

WRAPPER = Path('SideStore/Core/DeviceApi/MinimuxerWrapper.swift')
API = Path('DeviceGateway/DeviceGatewayAPI.swift')
MARK = 'SCARLET_V140_BONJOUR_ENDPOINT_RETRY'


def one(s,old,new,label):
    n=s.count(old)
    if n!=1:raise ValueError(f'V140 RP {label}: expected one anchor, found {n}')
    return s.replace(old,new,1)


def wrapper(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'restore_original_endpoint' not in s:
            raise ValueError('V140 RP partial implementation')
        return s
    if 'SCARLET_V138_RP_TYPED_UDID' not in s or 'withRemotePairingRetry' not in s:
        raise ValueError('V140 requires typed V138 RemotePairing source')
    start=s.index('private func resolveDiscoveredRemotePairingPort() async -> UInt16? {')
    end=s.index('\npublic var minimuxerStatusPublisher:',start)
    old=s[start:end]
    for marker in ('lastRemotePairingPortResolveTime', 'remotePairingPortCache = newPort',
                   'resolveDiscoveredRemotePairingPortThrottled()'):
        if marker not in old:raise ValueError('V140 unexpected original RP retry code: '+marker)
    replacement='''// SCARLET_V140_BONJOUR_ENDPOINT_RETRY: a port-only retry cannot repair
// a changed VPN peer or Bonjour endpoint when both expose the same port.
// Use the *resolved* host+port from the known rppairing service, never any
// random _http._tcp Bonjour record. RPPairing authenticates with the retained
// pairing record before it can count as a successful connection.
private var lastV140BonjourRetryTime: Date = .distantPast

private func resolveV140RemotePairingEndpoint() async -> (host: String, port: UInt16)? {
    guard let resolved = await BonjourDiscoveryManager.resolveFirstService(
        ofType: AppConstants.Minimuxer.remotePairingDaemonServiceType,
        timeout: AppConstants.Bonjour.defaultDiscoveryTimeout
    ) else { return nil }
    let octets = resolved.host.split(separator: ".", omittingEmptySubsequences: false)
    guard octets.count == 4,
          octets.allSatisfy({ UInt8(String($0)) != nil }),
          resolved.port > 0 else {
        debugLog("[SCARLET_V140_RP] discovery=invalid_endpoint fallback=preserved")
        return nil
    }
    return (host: resolved.host, port: resolved.port)
}

private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {
    do {
        return try await operation()
    } catch {
        let firstError = error
        let gateway = minimuxer.gateway
        guard gateway.pairingFileType == .rppairing else { throw firstError }
        // Avoid retry storms. Never treat an invalid record as a network fault.
        let message = String(describing: firstError).lowercased()
        if message.contains("invalidpairing") || message.contains("invalid pairing") {
            throw firstError
        }
        let now = Date()
        guard now.timeIntervalSince(lastV140BonjourRetryTime) >= 5 else {
            debugLog("[SCARLET_V140_RP] retry=throttled original_failure=retained")
            throw firstError
        }
        lastV140BonjourRetryTime = now
        guard let discovered = await resolveV140RemotePairingEndpoint() else {
            debugLog("[SCARLET_V140_RP] discovery=absent original_endpoint=retained")
            throw firstError
        }
        let previousHost = gateway.deviceEndpointIp
        let previousPort = gateway.getPort(for: .rppairing)
        if discovered.host == previousHost && discovered.port == previousPort {
            debugLog("[SCARLET_V140_RP] candidate=unchanged result=original_error")
            throw firstError
        }
        // Use only ephemeral in-memory transport values. NO changes to
        // pairing data, Keychain, saved VPN overrides, or provisioning IDs.
        debugLog("[SCARLET_V140_RP] candidate=bonjour host_changed=\\(discovered.host != previousHost) port_changed=\\(discovered.port != previousPort)")
        gateway.setDeviceEndpointIp(discovered.host)
        gateway.setPort(discovered.port, for: .rppairing)
        remotePairingPortCache = discovered.port
        do {
            let verified = try await operation()
            debugLog("[SCARLET_V140_RP] candidate=bonjour result=transport_success")
            return verified
        } catch {
            // restore_original_endpoint: fail closed, do not poison working
            // settings after an unrelated/unauthenticated mDNS candidate.
            gateway.setDeviceEndpointIp(previousHost)
            gateway.setPort(previousPort, for: .rppairing)
            remotePairingPortCache = previousPort
            debugLog("[SCARLET_V140_RP] candidate=bonjour result=failed original_endpoint=restored")
            throw error
        }
    }
}
'''
    return s[:start]+replacement+s[end:]


def api(s):
    if 'SCARLET_V140_ENDPOINT_GETTER' in s:
        if s.count('SCARLET_V140_ENDPOINT_GETTER')!=1:raise ValueError('duplicate getter marker')
        return s
    return one(s,'    var pairingFileType: PairingProtocol { get }',
        '''    var pairingFileType: PairingProtocol { get }
    // SCARLET_V140_ENDPOINT_GETTER: snapshot in-memory transport before
    // a one-shot Bonjour fallback; restoring is mandatory on failed proof.
    var deviceEndpointIp: String? { get }''',
        'existing gateway endpoint read access')


def apply(side:Path,mux:Path):
    changes=[]
    for file,fn in ((side/WRAPPER,wrapper),(mux/API,api)):
        if not file.is_file() or file.is_symlink():raise ValueError('missing pinned source '+str(file))
        before=file.read_text(encoding='utf-8')
        after=fn(before)
        if fn(after)!=after:raise ValueError('V140 RP non-idempotent '+str(file))
        changes.append((file,before,after))
    for file,before,after in changes:
        if before!=after:file.write_text(after,encoding='utf-8')
    print('[PASS] V140 RP compares host AND port; one authenticated retry; rollback on failure')

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: patch_v140_pairing_endpoint_retry.py <SideStore> <Minimuxer>')
    apply(Path(sys.argv[1]),Path(sys.argv[2]))
