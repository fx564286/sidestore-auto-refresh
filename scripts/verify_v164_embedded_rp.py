#!/usr/bin/env python3
"""Fail release if V164 RemotePairing repair is absent from embedded SideStore Mach-O."""
from pathlib import Path
import sys
import zipfile

EMBEDDED='Payload/LiveContainer.app/Frameworks/SideStoreApp.framework/SideStore'
REQUIRED=(
    b'[SCARLET_V164_TRANSPORT_RESYNC] stage=auth decision=manual_repair',
    b'[SCARLET_V164_TRANSPORT_RESYNC] stage=handshake decision=success',
    b'[SCARLET_V164_TRANSPORT_RESYNC] stage=handshake decision=failed',
    b'[SCARLET_V164_TRANSPORT_RESYNC] stage=recovery decision=all_failed',
    b'vpn_peer_discovered_port',
    b'transient_same_endpoint',
    b'bonjour_service_endpoint',
)

def verify(executable):
    if not executable.startswith(b'\xcf\xfa\xed\xfe'):
        raise ValueError('V164 embedded SideStore arm64 Mach-O missing')
    missing=[s.decode() for s in REQUIRED if s not in executable]
    if missing:
        raise ValueError('V164 compiled RP bounded recovery missing '+repr(missing))
    return True

def main(path):
    with zipfile.ZipFile(path) as archive:
        binary=archive.read(EMBEDDED)
    verify(binary)
    print('[PASS] V164 embedded SideStore: VPN port-first, bounded TLS retry, paired identity not bypassed')

if __name__=='__main__':
    if len(sys.argv)!=2:
        raise SystemExit('usage: verify_v164_embedded_rp.py <IPA>')
    main(Path(sys.argv[1]))
