#!/usr/bin/env python3
"""V166: complete the desktop-integrated RP Inbox handoff in the iOS app.

After the installer has verified a trusted USB RP record and staged it in the
app documents Inbox, the *existing* service validates/imports that file on
first launch. No unauthenticated pairing creation, bypass or new signer path.
"""
from pathlib import Path
import sys
SWIFT=Path('LiveContainerSwiftUI/Views/V3UnifiedShell.swift')
MARK='SCARLET_V166_AUTOMATIC_RP_HANDOFF'

def one(src,a,b,label):
    n=src.count(a)
    if n!=1:raise ValueError(f'V166 {label} anchor drift: {n}')
    return src.replace(a,b,1)

def patch(src):
    if MARK in src:
        if src.count('['+MARK+']')!=1 or 'SCARLET_V166_AUTO_IMPORT_ONCE' not in src:
            raise ValueError('V166 partial or duplicate patch')
        return src
    for marker in ('SCARLET_V165_SINGLE_NEXT_ACTION', 'SCARLET_V165_INBOX_REUSE',
                   'SCARLET_V165_FIRST_LAUNCH'):
        if marker not in src:raise ValueError('V166 requires V165: '+marker)
    src=one(src,'''    @State private var receivedPairingFile: URL?
    // SCARLET_V165_INBOX_REUSE:''','''    @State private var receivedPairingFile: URL?
    @State private var automaticImportAttempted = false
    // SCARLET_V165_INBOX_REUSE:''','state for one automatic import')
    src=one(src,'''        .onAppear { receivedPairingFile = Self.oneReceivedPairingFile() }
    }
    // V3_PAIRING_PLACEMENT_STEPS_V1''','''        .onAppear {
            receivedPairingFile = Self.oneReceivedPairingFile()
            // SCARLET_V166_AUTO_IMPORT_ONCE: the already-trusted PC tool
            // stages *one* RP file in Documents/Inbox; reuse the existing
            // validated service mutation, never write pairing data directly.
            guard !automaticImportAttempted,
                  let file = receivedPairingFile,
                  V3PairingPresentationPolicy.state(statusConnected: status.connected,
                    pairingStatus: status.pairing) == .unsatisfied,
                  !working else { return }
            automaticImportAttempted = true
            NSLog("[SCARLET_V166_AUTOMATIC_RP_HANDOFF] phase=import_requested keys=redacted")
            Task { await importFile(file) }
        }
    }
    // V3_PAIRING_PLACEMENT_STEPS_V1''', 'auto import when already staged and missing')
    src=one(src,'''            await setup.reloadAndRecalculate(status: status)
        }
        .onChange(of: status.jitlessReadiness) { readiness in''','''            await setup.reloadAndRecalculate(status: status)
            // Show the already-existing Pairing sheet automatically ONLY
            // after our USB installer staged its single stable Inbox file.
            // Absent files retain V165's manual recovery path.
            if (setup.pairing.state == "actionRequired" || setup.pairing.state == "failed"),
               let documents = FileManager.default.urls(for: .documentDirectory,
                    in: .userDomainMask).first,
               FileManager.default.fileExists(atPath: documents
                    .appendingPathComponent("Inbox/Scarlet-RemotePairing.plist").path) {
                showPairingSetup = true
            }
        }
        .onChange(of: status.jitlessReadiness) { readiness in''','automatic setup routing')
    return src

def apply(root):
    p=root/SWIFT
    if not p.is_file() or p.is_symlink():raise ValueError('V166 Swift shell source missing')
    old=p.read_text(encoding='utf-8');new=patch(old)
    if patch(new)!=new:raise ValueError('V166 patch not idempotent')
    if new!=old:p.write_text(new,encoding='utf-8')
    print('[PASS] V166 automatic trusted USB RP Inbox handoff; V165 import service retained')

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('usage: patch_v166... <LiveContainer>')
    apply(Path(sys.argv[1]))
