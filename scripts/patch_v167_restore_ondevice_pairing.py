#!/usr/bin/env python3
"""Restore the original SideStore/minimuxer WirelessPair API through V3's iOS UI.

No SideInstaller code, no PC flow, no new pairing protocol implementation.
Apple Settings still requests pairing approval. Existing records preserved unless
new pairing succeeds and is validated by the same original parser/manager.
"""
from pathlib import Path
import sys

MARK = 'SCARLET_V167_ORIGINAL_ONDEVICE_PAIR_RESTORE'

def replace_exact(s, old, new, name):
    n=s.count(old)
    if n!=1:raise ValueError(f'V167 drift {name}: expected 1, got {n}')
    return s.replace(old,new,1)

SERVICE = r'''
// SCARLET_V167_ORIGINAL_ONDEVICE_PAIR_RESTORE: the upstream SideStore/minimuxer
// already provides WirelessPairWrapper -> WirelessPairService.start(); V3's
// headless shell hid its view but should never have disabled the backend API.
// Only transient pairing status/PIN cross the authenticated in-app command
// channel. The pairing private key never crosses in an RPC response or log.
@MainActor
final class V3OriginalOnDevicePairingSession {
    static let shared = V3OriginalOnDevicePairingSession()
    private var phase = "idle"
    private var pin = ""
    private var detail = ""
    private var serviceName = ""
    private var stagedURL: URL?

    func status() -> [String: Any] {
        return ["phase": phase, "pin": pin, "detail": detail, "serviceName": serviceName]
    }

    func begin() -> [String: Any] {
        if phase == "waiting" || phase == "pin" { return status() }
        NSLog("[SCARLET_V167_ONDEVICE_HOST] phase=start pin=redacted")
        // Starting from the dedicated user button is explicit consent to
        // retry even if a syntactically valid, stale pairing record exists.
        // Do not remove the earlier record until a new pair validates.
        phase = "waiting"
        pin = ""
        detail = "In Settings > Privacy & Security > Developer Mode, select Pair with SideStore."
        serviceName = ""
        let out = FileManager.default.temporaryDirectory
            .appendingPathComponent("scarlet-ondevice-" + UUID().uuidString + ".plist")
        stagedURL = out
        wirelessPairing.onReadyToPair = { [weak self] name, _ in
            Task { @MainActor in self?.serviceName = name }
        }
        wirelessPairing.onPinReceived = { [weak self] suppliedPin in
            Task { @MainActor in
                guard let self, self.phase == "waiting" || self.phase == "pin" else { return }
                // Do not put a pairing PIN into diagnostic output.
                self.pin = suppliedPin
                self.phase = "pin"
                self.detail = "Enter the displayed code in iOS Settings"
            }
        }
        wirelessPairing.start(outPath: out.path) { [weak self] result in
            Task { @MainActor in
                guard let self, self.stagedURL == out,
                      self.phase == "waiting" || self.phase == "pin" else { return }
                self.pin = ""
                switch result {
                case .success(let device):
                    // Preserve the original data until the new record parses.
                    // The upstream importer remains the source of truth.
                    do {
                        let contents = try String(contentsOfFile: device.pairingFilePath,
                                                  encoding: .utf8)
                        guard (try? PairingFileParser.parse(content: contents)) != nil else {
                            throw OperationError.invalidPairingFile(reason: "on-device record did not validate")
                        }
                        try PairingFileManager.shared.savePairingFile(contents: contents)
                        self.phase = "complete"
                        self.detail = "On-device pairing saved and validated"
                    } catch {
                        self.phase = "failed"
                        self.detail = "Pairing record was not accepted; previous record preserved"
                    }
                case .failure:
                    self.phase = "failed"
                    self.detail = "On-device pairing was not completed; retry from Settings"
                }
                self.stagedURL = nil
                try? FileManager.default.removeItem(at: out)
            }
        }
        return status()
    }

    func stop() -> [String: Any] {
        guard phase == "waiting" || phase == "pin" else { return status() }
        phase = "idle"
        pin = ""
        detail = "Pairing cancelled"
        wirelessPairing.stop()
        if let out = stagedURL { try? FileManager.default.removeItem(at: out) }
        stagedURL = nil
        return status()
    }
}
'''

UI = r'''
            // SCARLET_V167_ORIGINAL_ONDEVICE_PAIR_RESTORE: reuse the original
            // SideStore WirelessPair API, not an external PC pairing tool.
            Section("Pair on This iPhone") {
                // V168: a syntactically valid saved record can still fail the
                // authenticated RemotePairing handshake. Keep explicit re-pair
                // accessible even when the cached status claims satisfaction.
                // Only user activation starts pairing; no records are deleted.
                Button("Pair on This iPhone", systemImage: "iphone.gen3.radiowaves.left.and.right") {
                        Task { await onDevicePairCommand("wirelessPairStart") }
                    }
                    .disabled(working || onDevicePairPhase == "waiting" || onDevicePairPhase == "pin")
                    .accessibilityIdentifier("scarletV167OnDevicePair")
                    Text("Open iOS Settings > Privacy & Security > Developer Mode > Pair with a device. Select the advertised host and approve Apple's pairing request.")
                        .font(.footnote).foregroundColor(.secondary)
                if onDevicePairPhase == "waiting" || onDevicePairPhase == "pin" {
                    Text("Pairing host: SideStore").font(.caption)
                    Label("Waiting for iPhone pairing approval", systemImage: "antenna.radiowaves.left.and.right")
                    if !onDevicePairPin.isEmpty {
                        Text("Pairing code: " + onDevicePairPin)
                            .font(.title2.monospacedDigit().bold())
                            .accessibilityIdentifier("scarletV167PairingPIN")
                    }
                    Button("Check Pairing", systemImage: "arrow.clockwise") {
                        Task { await onDevicePairCommand("wirelessPairStatus") }
                    }
                    Button("Cancel Pairing", role: .cancel) {
                        Task { await onDevicePairCommand("wirelessPairStop") }
                    }
                }
                if onDevicePairPhase == "complete" {
                    Label("On-device pairing record saved", systemImage: "checkmark.seal.fill")
                } else if onDevicePairPhase == "failed" {
                    Text("Pairing did not finish. Previous records were not deleted.")
                        .font(.footnote).foregroundColor(.red)
                }
                if !onDevicePairDetail.isEmpty {
                    Text(onDevicePairDetail).font(.caption).foregroundColor(.secondary)
                }
            }
'''

METHOD = r'''
    // The existing V3 SideStore service owns the native pairing listener.
    // This view holds no keys and does not fake an authenticated connection.
    private func onDevicePairCommand(_ operation: String) async {
        if operation == "wirelessPairStart" {
            NSLog("[SCARLET_V167_ONDEVICE_UI] action=start")
        }
        do {
            let reply = try await V3ServiceBridge.shared.request(operation: operation)
            onDevicePairPhase = reply["phase"] as? String ?? "unknown"
            onDevicePairPin = reply["pin"] as? String ?? ""
            onDevicePairDetail = reply["detail"] as? String ?? ""
            if onDevicePairPhase == "complete" { status.reload() }
        } catch {
            onDevicePairPhase = "failed"
            onDevicePairPin = ""
            onDevicePairDetail = V3FailureGuidance.message(error)
        }
    }
'''

def patch_wire(src):
    if MARK in src:
        for item in ('"wirelessPairStart"','"wirelessPairStop"','"wirelessPairStatus"'):
            if item not in src:raise ValueError('V167 wire partial '+item)
        return src
    src=replace_exact(src,'"pairingImportData", "settingsGet", "settingsSet",',
        '"pairingImportData", "wirelessPairStart", "wirelessPairStatus", "wirelessPairStop", "settingsGet", "settingsSet",',
        'wire operations')
    src=replace_exact(src,'"sourcePreview", "settingsGet",',
        '"sourcePreview", "settingsGet", "wirelessPairStatus",', 'wire read-only')
    src=replace_exact(src,'"sidesignReset", "sidesignExport", "anisetteList", "anisetteReset", "anisetteSync",',
        '"sidesignReset", "sidesignExport", "anisetteList", "anisetteReset", "anisetteSync", "wirelessPairStart", "wirelessPairStop", "wirelessPairStatus",',
        'wire zero-target')
    # Avoid unsafe matching in the token-required set: the new ops are empty target.
    return src + "\n// " + MARK + ": shared wire contract restored.\n"

def patch_service(src):
    if 'final class V3OriginalOnDevicePairingSession' in src:
        if src.count('final class V3OriginalOnDevicePairingSession')!=1:raise ValueError('V167 service partial')
        return src
    src=replace_exact(src,'// V3_SIDESTORE_COMMAND_SERVICE_V1',SERVICE+'\n// V3_SIDESTORE_COMMAND_SERVICE_V1','add native gateway')
    src=replace_exact(src,'        case "pairingImportData":\n            try V3BackendCommands.pairingImportData(token: target)',
    '''        case "wirelessPairStart":
            return V3OriginalOnDevicePairingSession.shared.begin()
        case "wirelessPairStatus":
            return V3OriginalOnDevicePairingSession.shared.status()
        case "wirelessPairStop":
            return V3OriginalOnDevicePairingSession.shared.stop()
        case "pairingImportData":
            try V3BackendCommands.pairingImportData(token: target)''','route original pair service')
    return src

def patch_host(src):
    if MARK in src:
        if 'scarletV167OnDevicePair' not in src:raise ValueError('V167 UI partial')
        return src
    src=replace_exact(src,'    @State private var receivedPairingFile: URL?',
    r'''    @State private var onDevicePairPhase = "idle"
    @State private var onDevicePairPin = ""
    @State private var onDevicePairDetail = ""
    @Environment(\.scenePhase) private var nativePairScenePhase
    @State private var receivedPairingFile: URL?''','host state')
    src=replace_exact(src,'            Section("Status") {\n                HStack {\n                    Text("Pairing Status")',UI+'\n            Section("Status") {\n                HStack {\n                    Text("Pairing Status")','native pairing UI')
    src=replace_exact(src,'        .onAppear {\n            receivedPairingFile = Self.oneReceivedPairingFile()',
    '''        .onChange(of: nativePairScenePhase) { phase in
            if phase == .active {
                Task { await onDevicePairCommand("wirelessPairStatus") }
            }
        }
        .onAppear {
            Task { await onDevicePairCommand("wirelessPairStatus") }
            receivedPairingFile = Self.oneReceivedPairingFile()''','return from iOS Settings')
    src=replace_exact(src,'    // V3_PAIRING_PLACEMENT_STEPS_V1',METHOD+'\n    // V3_PAIRING_PLACEMENT_STEPS_V1','native method')
    return src

def patch_pairing_storage(src):
    marker = 'SCARLET_V167_ATOMIC_PAIRING_PRESERVE'
    if marker in src: return src
    old = '''        if fm.fileExists(atPath: documentsPath.path) {
            try? fm.removeItem(at: documentsPath)
        }
        try contents.write(to: documentsPath, atomically: true, encoding: .utf8)'''
    new = '''        // SCARLET_V167_ATOMIC_PAIRING_PRESERVE: never delete a previous
        // working record before atomically installing its replacement.
        try contents.write(to: documentsPath, atomically: true, encoding: .utf8)'''
    return replace_exact(src,old,new,'atomic upstream pairing save')

def patch_wireless_log(src):
    marker = 'SCARLET_V167_PIN_LOG_REDACTION'
    if marker in src:return src
    old = r'''debugLog("[WirelessPairService] gateway onPin callback (pin='\(pinString)')")'''
    new = '''debugLog("[WirelessPairService] SCARLET_V167_PIN_LOG_REDACTION callback received (pin=redacted)")'''
    return replace_exact(src,old,new,'private PIN log removal')

def apply(live, side):
    files=[(live/'SideStoreSupport/SideStore.swift',patch_wire),
           (side/'AltStore/AppDelegate.swift',lambda s:patch_service(patch_wire(s))),
           (side/'SideStore/Core/Pairing/PairingFileManager.swift',patch_pairing_storage),
           (side/'Dependencies/minimuxer/Sources/Services/WirelessPairService.swift',patch_wireless_log),
           (live/'LiveContainerSwiftUI/Views/V3UnifiedShell.swift',patch_host)]
    writes=[]
    for p,fn in files:
        if not p.is_file() or p.is_symlink():raise ValueError('V167 expected host file missing: '+str(p))
        old=p.read_text(encoding='utf-8');new=fn(old)
        if fn(new)!=new:raise ValueError('V167 non-idempotent patch '+str(p))
        writes.append((p,old,new))
    for p,old,new in writes:
        if old!=new:p.write_text(new,encoding='utf-8')
    print('[PASS] V167 original SideStore on-device WirelessPair API restored to V3 shell')

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('usage: patch_v167_restore_ondevice_pairing.py <LiveContainer> <SideStore>')
    apply(Path(sys.argv[1]),Path(sys.argv[2]))
