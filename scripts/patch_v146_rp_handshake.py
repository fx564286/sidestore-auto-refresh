#!/usr/bin/env python3
"""V146: separate TCP reachability from authenticated RemotePairing readiness.

Do not replace pairing material, guess device IDs, bypass signing, or mutate
IP/ports. Suppress premature start probes on missing route and record typed
diagnostics for a socket that accepts TCP then resets its RP handshake.
"""
from pathlib import Path
import sys
FILE=Path("SideStore/Core/DeviceApi/MinimuxerWrapper.swift")
MARK="SCARLET_V146_RP_HANDSHAKE_DIAGNOSTICS"

def one(s,a,b,why):
    n=s.count(a)
    if n!=1:raise ValueError(f"V146 RP {why}: expected 1 found {n}")
    return s.replace(a,b,1)

def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or "route_missing" not in s or "transport_verified=false" not in s:
            raise ValueError("V146 partial remote pairing probe")
        return s
    if "SCARLET_V142_NETWORK_GENERATION_GUARD" not in s:
        raise ValueError("V146 requires prior route generation guard")
    s=one(s,
'''    debugLog("[SideStore] fetchUDID() invoked")
    // SCARLET_V138_RP_TYPED_UDID: do not swallow transport failure into nil''',
'''    debugLog("[SideStore] fetchUDID() invoked")
    // SCARLET_V146_RP_HANDSHAKE_DIAGNOSTICS: before the VPN route exists, a probe cannot succeed.
    // Do not interpret a pairing file's cached UDID as live validation.
    if minimuxer.gateway.pairingFileType == .rppairing,
       minimuxer.gateway.deviceEndpointIp == nil {
        debugLog("[SCARLET_V146_RP] state=route_missing transport_verified=false")
        return useStatic ? PairingFileManager.shared.pairingUDID : nil
    }
    // SCARLET_V138_RP_TYPED_UDID: do not swallow transport failure into nil''',"do not probe nil RP peer")
    s=one(s,
'''    } catch {
        if useStatic {
            debugLog("[SCARLET_V138_RP] stage=udid fallback=static requested=true verified=false")''',
r'''    } catch {
        // V146: distinguish a TCP port accepting probes from a successful
        // authenticated RemotePairing handshake, without logging secrets.
        let transportDescription = String(describing: error).lowercased()
        let peerReset = transportDescription.contains("connectionreset") ||
                        transportDescription.contains("connection reset") ||
                        transportDescription.contains("code: 54")
        debugLog("[SCARLET_V146_RP] handshake=failed reset=\(peerReset) transport_verified=false")
        if useStatic {
            debugLog("[SCARLET_V138_RP] stage=udid fallback=static requested=true verified=false")''',
        "typed RP reset diagnostic on failed UDID")
    return s

def apply(root):
    p=root/FILE
    if not p.is_file() or p.is_symlink():raise ValueError("V146 pinned transport source missing")
    old=p.read_text(encoding="utf-8")
    new=patch(old)
    if patch(new)!=new:raise ValueError("V146 transport patch not idempotent")
    if old!=new:p.write_text(new,encoding="utf-8")
    print("[PASS] V146 RP nil-route probe guard and explicit unverified-handshake diagnostics")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v146_rp_handshake.py <EmbeddedSideStore>")
    apply(Path(sys.argv[1]))
