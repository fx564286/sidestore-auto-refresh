#!/usr/bin/env python3
"""V142: prevent stale RemotePairing host restoration across VPN handoffs.

Patch only the existing V140 bounded fallback; preserve signing, pair records,
app containers, JIT flags and explicit user preferences. A disappearing VPN
must not be reconstituted by a delayed Bonjour retry.
"""
from pathlib import Path
import sys
SOURCE=Path('SideStore/Core/DeviceApi/MinimuxerWrapper.swift')
MARK='SCARLET_V142_NETWORK_GENERATION_GUARD'

def one(s,old,new,why):
    count=s.count(old)
    if count!=1:raise ValueError(f'V142 {why}: expected one anchor, got {count}')
    return s.replace(old,new,1)

def wrapper(s):
    if MARK in s:
        if s.count(MARK)!=1 or 'network_handoff_skipped' not in s or 'route_changed_not_restored' not in s:
            raise ValueError('partial V142 route guard')
        return s
    if 'SCARLET_V140_BONJOUR_ENDPOINT_RETRY' not in s:
        raise ValueError('V142 requires compiled V140 endpoint fallback')
    s=one(s,
        '''    let octets = resolved.host.split(separator: ".", omittingEmptySubsequences: false)''',
        '''    // IPv6 loopback is this iPhone, not a remote VPN peer. A Bonjour
    // candidate is not proof of an authenticated paired endpoint.
    if resolved.host == "::1" || resolved.host == "127.0.0.1" ||
       resolved.host.lowercased() == "localhost" {
        debugLog("[SCARLET_V142_RP] discovery=loopback_ignored verified=false")
        return nil
    }
    let octets = resolved.host.split(separator: ".", omittingEmptySubsequences: false)''',
        'explicit IPv6 localhost classification')
    s=one(s,
        '''        guard gateway.pairingFileType == .rppairing else { throw firstError }
        // Avoid retry storms.''',
        '''        guard gateway.pairingFileType == .rppairing else { throw firstError }
        // SCARLET_V142_NETWORK_GENERATION_GUARD: the VPN observer may clear
        // its route after the failing transport attempt. Never restart
        // a stale host from cached reachability or from Bonjour localhost.
        guard let peerBeforeDiscovery = gateway.deviceEndpointIp,
              !peerBeforeDiscovery.isEmpty else {
            debugLog("[SCARLET_V142_RP] retry=network_unavailable verified=false")
            throw firstError
        }
        // Avoid retry storms.''',
        'guard VPN peer before DNS-SD await')
    s=one(s,
        '''        guard let discovered = await resolveV140RemotePairingEndpoint() else {
            debugLog("[SCARLET_V140_RP] discovery=absent original_endpoint=retained")
            throw firstError
        }
        let previousHost = gateway.deviceEndpointIp''',
        '''        guard let discovered = await resolveV140RemotePairingEndpoint() else {
            debugLog("[SCARLET_V140_RP] discovery=absent original_endpoint=retained")
            throw firstError
        }
        // DNS-SD can outlive a cellular/VPN route change. Do not use a
        // candidate or restore the old route after the observer cleared it.
        guard gateway.deviceEndpointIp == peerBeforeDiscovery else {
            debugLog("[SCARLET_V142_RP] retry=network_handoff_skipped verified=false")
            throw firstError
        }
        let previousHost = gateway.deviceEndpointIp''',
        'compare network state after asynchronous discovery')
    s=one(s,
        '''            gateway.setDeviceEndpointIp(previousHost)
            gateway.setPort(previousPort, for: .rppairing)
            remotePairingPortCache = previousPort
            debugLog("[SCARLET_V140_RP] candidate=bonjour result=failed original_endpoint=restored")''',
        '''            // The network observer owns endpoint invalidation. Only
            // restore if the temporary Bonjour host is STILL current.
            if gateway.deviceEndpointIp == discovered.host &&
               gateway.getPort(for: .rppairing) == discovered.port {
                gateway.setDeviceEndpointIp(previousHost)
                gateway.setPort(previousPort, for: .rppairing)
                remotePairingPortCache = previousPort
                debugLog("[SCARLET_V142_RP] candidate=bonjour result=failed original_endpoint=restored")
            } else {
                // Avoid writing the stale peer after uTun disappeared.
                if remotePairingPortCache == discovered.port {
                    remotePairingPortCache = previousPort
                }
                debugLog("[SCARLET_V142_RP] candidate=bonjour result=route_changed_not_restored")
            }''',
        'do not overwrite network observer on fallback failure')
    return s

def apply(root:Path):
    p=root/SOURCE
    if not p.is_file() or p.is_symlink():raise ValueError('missing pinned SideStore source')
    old=p.read_text(encoding='utf-8'); new=wrapper(old)
    if wrapper(new)!=new:raise ValueError('V142 not idempotent')
    if new!=old:p.write_text(new,encoding='utf-8')
    print('[PASS] V142 route generation guard, loopback refusal and no stale endpoint restoration')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v142_pairing_route_race.py <SideStore>')
    apply(Path(sys.argv[1]))
