#!/usr/bin/env python3
"""V172 source-level parity review: trust this iPhone's RP service advertisement.

Independently implemented after examining SideInstaller's documented RP
endpoint selection. It does not vendor SideInstaller's custom-licensed code,
replace credentials, change pairing records, or claim a successful TLS tunnel.

The embedded gateway must dial the active LocalDevVPN *peer*, not the phone's
Wi-Fi IP. DNS-SD is useful as a source of the *port*, but only when the
advertisement resolves to an IP address owned by this same iPhone.
"""
from pathlib import Path
import sys

SOURCE = Path("SideStore/Core/DeviceApi/MinimuxerWrapper.swift")
MARK = "SCARLET_V172_OWN_DEVICE_RP_ADVERT"

# Native IPv4 verification; iOS advertises its own service using an interface
# address. Reject advertisements for other phones on the same LAN.
HELPER = """// SCARLET_V172_OWN_DEVICE_RP_ADVERT: refuse an unrelated LAN host.
private func scarletV172IsOwnAdvertisedIPv4(_ host: String) -> Bool {
    var interfaces: UnsafeMutablePointer<ifaddrs>?
    guard getifaddrs(&interfaces) == 0, let first = interfaces else { return false }
    defer { freeifaddrs(first) }
    var cursor: UnsafeMutablePointer<ifaddrs>? = first
    while let current = cursor {
        cursor = current.pointee.ifa_next
        guard let addr = current.pointee.ifa_addr,
              addr.pointee.sa_family == sa_family_t(AF_INET) else { continue }
        var ip = UnsafeRawPointer(addr).assumingMemoryBound(to: sockaddr_in.self).pointee.sin_addr
        var buffer = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
        guard inet_ntop(AF_INET, &ip, &buffer, socklen_t(buffer.count)) != nil else { continue }
        if String(cString: buffer) == host { return true }
    }
    return false
}

"""

SERVICE_RETURN = "    return (host: resolved.host, port: resolved.port)"
SERVICE_CHECK = """    // The SideInstaller REA showed that _remotepairing._tcp can include
    // unrelated devices. It must describe *this* iPhone, not the first host.
    guard scarletV172IsOwnAdvertisedIPv4(resolved.host) else {
        debugLog("[SCARLET_V172_RP] stage=discovery own_host=false candidate=discarded")
        return nil
    }
    return (host: resolved.host, port: resolved.port)"""

WIFI_CANDIDATE = """        if let discovered,
           (discovered.host != initialHost || discovered.port != initialPort) {
            candidates.append((discovered.host, discovered.port, "bonjour_service_endpoint"))
        }
"""
PEER_ONLY = """        // SCARLET_V172: DNS-SD supplies the listener PORT, never the Wi-Fi
        // address as a replacement for the authenticated VPN peer. Connecting
        // to the phone's Wi-Fi address from its own process is not equivalent
        // to the LocalDevVPN tunnel. Keep original peer/port after failures.
"""

def patch(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or "scarletV172IsOwnAdvertisedIPv4(resolved.host)" not in source:
            raise ValueError("V172 only partly applied")
        if "bonjour_service_endpoint" in source:
            raise ValueError("V172 untrusted host retry remains")
        return source
    for marker in ("SCARLET_V164_TRANSPORT_RESYNC",
                   "SCARLET_V170_RP_HANDSHAKE_RESET",
                   "private func resolveV140RemotePairingEndpoint()",
                   "private func withRemotePairingRetry<T>("):
        if marker not in source:
            raise ValueError("V172 required source absent: " + marker)
    if source.count(SERVICE_RETURN) != 1:
        raise ValueError("V172 expected exactly one DNS-SD return")
    if source.count(WIFI_CANDIDATE) != 1:
        raise ValueError("V172 expected exactly one LAN retry block")
    if source.count("import Foundation\n") != 1:
        raise ValueError("V172 unexpected Swift import layout")
    result = source.replace("import Foundation\n", "import Foundation\nimport Darwin\n", 1)
    result = result.replace(
        "private func resolveV140RemotePairingEndpoint()",
        HELPER + "private func resolveV140RemotePairingEndpoint()", 1
    )
    result = result.replace(SERVICE_RETURN, SERVICE_CHECK, 1)
    result = result.replace(WIFI_CANDIDATE, PEER_ONLY, 1)
    return result

def apply(root: Path) -> None:
    target = root / SOURCE
    if not target.is_file() or target.is_symlink():
        raise ValueError("V172 embedded SideStore wrapper missing")
    before = target.read_text(encoding="utf-8")
    after = patch(before)
    if patch(after) != after:
        raise ValueError("V172 patch not idempotent")
    if before != after:
        target.write_text(after, encoding="utf-8")
    print("[PASS] V172 own-iPhone DNS-SD verification; VPN peer retained; pairing untouched")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v172_sideinstaller_transport.py <EmbeddedSideStore>")
    apply(Path(sys.argv[1]))
