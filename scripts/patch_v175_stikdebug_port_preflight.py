#!/usr/bin/env python3
"""V175: discover this iPhone's RP listener port before the first handshake.

Independent implementation informed by StikDebug's proactive DNS-SD port
resolver and SideInstaller's own-device advertisement verification.
Requires V172's own-host check. No saved pairing data/credentials or network
preferences are changed; tentative port changes roll back after failure.
"""
from pathlib import Path
import sys

SOURCE = Path("SideStore/Core/DeviceApi/MinimuxerWrapper.swift")
MARKER = "SCARLET_V175_STIKDEBUG_PORT_PREFLIGHT"
ENTRY = """private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {
    do {
"""

NEW_ENTRY = """private func withRemotePairingRetry<T>(_ operation: () async throws -> T) async throws -> T {
    // SCARLET_V175_STIKDEBUG_PORT_PREFLIGHT: test the actual listener port
    // before blindly reaching the familiar 49152 endpoint. DNS-SD supplies
    // only a port from this phone's own interface; the VPN peer IP remains.
    let v175Gateway = minimuxer.gateway
    if v175Gateway.pairingFileType == .rppairing,
       let v175Host = v175Gateway.deviceEndpointIp, !v175Host.isEmpty {
        let v175OriginalPort = v175Gateway.getPort(for: .rppairing)
        if let v175Advert = await resolveV140RemotePairingEndpoint(),
           v175Advert.port != v175OriginalPort,
           v175Gateway.deviceEndpointIp == v175Host,
           v175Gateway.getPort(for: .rppairing) == v175OriginalPort {
            v175Gateway.setPort(v175Advert.port, for: .rppairing)
            NSLog("[SCARLET_V175_RP] stage=preflight advertised_port=selected record=preserved")
            do {
                let verified = try await operation()
                remotePairingPortCache = v175Advert.port
                NSLog("[SCARLET_V175_RP] stage=preflight result=authenticated")
                return verified
            } catch {
                // Identity rejection isn't a port-routing problem.
                let message = String(describing: error).lowercased()
                if v175Gateway.deviceEndpointIp == v175Host &&
                   v175Gateway.getPort(for: .rppairing) == v175Advert.port {
                    v175Gateway.setPort(v175OriginalPort, for: .rppairing)
                    remotePairingPortCache = v175OriginalPort
                }
                if message.contains("invalidpairing") ||
                   message.contains("invalid pairing") ||
                   message.contains("pairverifyfailed") {
                    throw error
                }
                NSLog("[SCARLET_V175_RP] stage=preflight result=unverified restored=true")
            }
        }
    }
    do {
"""

def patch(source: str) -> str:
    if MARKER in source:
        if source.count(MARKER) != 1 or "v175Gateway.setPort(v175OriginalPort" not in source:
            raise ValueError("V175 source was partially patched")
        return source
    if "SCARLET_V172_OWN_DEVICE_RP_ADVERT" not in source:
        raise ValueError("V175 requires V172 own-device DNS-SD verification")
    if source.count(ENTRY) != 1:
        raise ValueError("V175 expected exactly one RP retry entry")
    return source.replace(ENTRY, NEW_ENTRY, 1)

def apply(root: Path):
    target = root / SOURCE
    if not target.is_file() or target.is_symlink():
        raise ValueError("V175 embedded SideStore wrapper missing")
    before = target.read_text(encoding="utf-8")
    after = patch(before)
    if patch(after) != after:
        raise ValueError("V175 patch not idempotent")
    if before != after:
        target.write_text(after, encoding="utf-8")
    print("[PASS] V175 own-device port preflight, rollback without record writes")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v175_stikdebug_port_preflight.py <EmbeddedSideStore>")
    apply(Path(sys.argv[1]))
