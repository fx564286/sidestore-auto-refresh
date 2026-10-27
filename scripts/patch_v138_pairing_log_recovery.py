#!/usr/bin/env python3
"""V138: correct misleading RemotePairing reset/UDID state in the shipped sources.

ConnectionReset is a transport error, NOT proof of an invalid pairing record.
Never replace/decrypt/delete the user's existing record, certificate or keys.
Do not infer real JIT activation from the absence of a SideJIT server.
"""
from pathlib import Path
import sys

GATEWAY=Path('DeviceGateway/idevice/IdeviceGateway.swift')
WRAPPER=Path('SideStore/Core/DeviceApi/MinimuxerWrapper.swift')
BOOT=Path('SideStore/AppBootManager.swift')
MARK='SCARLET_V138_RP_ERROR_CLASSIFICATION'


def one(body, old, new, description):
    count=body.count(old)
    if count!=1:raise ValueError(f'{description}: expected 1 anchor, got {count}')
    return body.replace(old,new,1)


def gateway(body):
    if MARK in body:
        if body.count(MARK)!=1:raise ValueError('duplicate RP classification marker')
        return body
    old='''            if msg.contains("invalidconf") || msg.contains("pairing") || msg.contains("handshake") ||
                msg.contains("connection reset") || msg.contains("connectionreset") {'''
    new='''            // SCARLET_V138_RP_ERROR_CLASSIFICATION: ECONNRESET is transport
            // failure, not evidence the user's pairing file is invalid.
            if msg.contains("invalidconf") || msg.contains("pairing") || msg.contains("handshake") {'''
    body=one(body,old,new,'gateway RP classifier')
    return body


def wrapper(body):
    marker='SCARLET_V138_RP_TYPED_UDID'
    if marker in body:
        if body.count(marker)!=1:raise ValueError('duplicate typed-UDID marker')
        return body
    old='''    let result = try? await withRemotePairingRetry {
        try await minimuxer.core.fetchUDID()
    }
    if let udid = result ?? nil, !udid.isEmpty, udid != "XXXXX-XXXX-XXXXX-XXXX" {
        return udid
    }
    if useStatic {
        return PairingFileManager.shared.pairingUDID
    }
    return nil'''
    new='''    // SCARLET_V138_RP_TYPED_UDID: do not swallow transport failure into nil
    // and then let the app boot report a successful verified-device test.
    // Keep the explicit useStatic fallback for existing offline JIT flows.
    let observed: String?
    do {
        observed = try await withRemotePairingRetry {
            try await minimuxer.core.fetchUDID()
        }
    } catch {
        if useStatic {
            debugLog("[SCARLET_V138_RP] stage=udid fallback=static requested=true verified=false")
            return PairingFileManager.shared.pairingUDID
        }
        debugLog("[SCARLET_V138_RP] stage=udid transport_error=propagated verified=false")
        throw error
    }
    if let udid = observed, !udid.isEmpty, udid != "XXXXX-XXXX-XXXXX-XXXX" {
        debugLog("[SCARLET_V138_RP] stage=udid result=verified via=transport")
        return udid
    }
    if useStatic {
        debugLog("[SCARLET_V138_RP] stage=udid fallback=static requested=true verified=false")
        return PairingFileManager.shared.pairingUDID
    }
    debugLog("[SCARLET_V138_RP] stage=udid result=unavailable verified=false")
    return nil'''
    return one(body,old,new,'UDID wrapper typed failure')


def boot(body):
    marker='SCARLET_V138_BOOT_VALIDATION'
    if marker in body:
        if body.count(marker)!=1:raise ValueError('duplicate boot validation')
        return body
    old='''            let deviceUDID = try await fetchUDID()
            debugLog("[AppBootManager] startMinimuxer(): Minimuxer fetchUDID() based connection test SUCCEEDED. UDID: \\(deviceUDID ?? "nil")")
            self.needsPairingPrompt = false'''
    new='''            // SCARLET_V138_BOOT_VALIDATION: nil is NOT success and a missing
            // device is NOT a reason to remove/recreate valid pairing data.
            guard let deviceUDID = try await fetchUDID(), !deviceUDID.isEmpty else {
                throw MinimuxerError.noDevice("RemotePairing did not return a verified UDID")
            }
            debugLog("[SCARLET_V138_RP] stage=boot result=verified_udid no_secret_logged=1")
            self.needsPairingPrompt = false'''
    return one(body,old,new,'boot non-nil UDID requirement')


def apply(side:Path, mux:Path):
    transformations=((mux/GATEWAY,gateway),(side/WRAPPER,wrapper),(side/BOOT,boot))
    pending=[]
    for path,fn in transformations:
        if not path.is_file() or path.is_symlink():
            raise ValueError('Unsafe or missing pinned source: '+str(path))
        raw=path.read_text(encoding='utf-8')
        patched=fn(raw)
        if fn(patched)!=patched:raise ValueError('V138 non-idempotent: '+str(path))
        pending.append((path,raw,patched))
    for path,raw,patched in pending:
        if raw!=patched:path.write_text(patched,encoding='utf-8')
    print('[PASS] V138 RP resets classified as transport; typed UDID error; no fake boot success')

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: script SIDESTORE_ROOT MINIMUXER_ROOT')
    apply(Path(sys.argv[1]),Path(sys.argv[2]))
