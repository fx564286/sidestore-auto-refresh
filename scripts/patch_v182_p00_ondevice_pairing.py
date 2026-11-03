#!/usr/bin/env python3
"""P00 pairing-first recovery for the V181 combined-source build.

Apply *after* V167's original WirelessPair adapter and V170's typed command
error adapter. Patches only the pairing + Apple 2FA entry surfaces and
SideStore's ephemeral pairing service, not Scarlet's Liquid Glass/dock code.

The PIN created by WirelessPairService is NOT an Apple ID 2FA code.
Apple-issued 2FA codes stay with Apple's trusted-device/SMS delivery and are
entered manually or via iOS's oneTimeCode autofill.
"""
from pathlib import Path
import sys

MARK = "SCARLET_V182_P00_PAIRING"
HOST = Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
SERVICE = Path("AltStore/AppDelegate.swift")


def once(source: str, before: str, after: str, label: str) -> str:
    matches = source.count(before)
    if matches != 1:
        raise ValueError(f"P00 {label}: expected one source anchor, got {matches}")
    return source.replace(before, after, 1)


def patch_service(source: str) -> str:
    if MARK in source:
        if source.count(MARK) != 1 or "lastNotifiedPairingPIN" not in source:
            raise ValueError("P00 incomplete SideStore pairing notification patch")
        return source
    if "SCARLET_V167_ORIGINAL_ONDEVICE_PAIR_RESTORE" not in source:
        raise ValueError("P00 requires the original SideStore WirelessPair bridge")
    if "import UserNotifications" not in source:
        raise ValueError("P00 requires SideStore's existing UserNotifications import")

    source = once(
        source,
        "    private var stagedURL: URL?\n\n    func status()",
        "    // " + MARK + ": notification is best-effort; never write the PIN to logs/defaults.\n"
        "    private var lastNotifiedPairingPIN = \"\"\n"
        "    private var stagedURL: URL?\n\n    func status()",
        "ephemeral notification state",
    )
    source = once(
        source,
        '        phase = "waiting"\n        pin = ""\n',
        '        phase = "waiting"\n        pin = ""\n        lastNotifiedPairingPIN = ""\n',
        "new pairing attempt resets notification ownership",
    )
    source = once(
        source,
        '''                self.detail = "Enter the displayed code in iOS Settings"
''',
        '''                self.detail = "Enter the displayed pairing code in iOS Settings"
                // Send only a PIN supplied by WirelessPairService for the
                // explicit pairing session. Never scrape Apple ID/SMS 2FA.
                // If the user denied notifications, the existing in-app code
                // remains the canonical fallback; pairing never waits for UN.
                let pairingPIN = suppliedPin
                let isSixASCIIDigits = pairingPIN.utf8.count == 6 &&
                    pairingPIN.unicodeScalars.allSatisfy {
                        $0.value >= 48 && $0.value <= 57
                    }
                if isSixASCIIDigits && self.lastNotifiedPairingPIN != pairingPIN {
                    self.lastNotifiedPairingPIN = pairingPIN
                    Task { @MainActor in
                        // The headless extension may not own notification
                        // authorization on every re-signed host: best effort.
                        let center = UNUserNotificationCenter.current()
                        let settings = await center.notificationSettings()
                        guard settings.authorizationStatus == .authorized ||
                              settings.authorizationStatus == .provisional else { return }
                        let content = UNMutableNotificationContent()
                        content.title = "Scarlet Crystal: Device Pairing"
                        content.body = "Pairing code: " + pairingPIN +
                            ". Enter this code in the iPhone pairing prompt."
                        content.sound = .default
                        let request = UNNotificationRequest(
                            identifier: "scarlet-ondevice-pair-pin",
                            content: content,
                            trigger: UNTimeIntervalNotificationTrigger(
                                timeInterval: 1, repeats: false))
                        try? await center.add(request)
                    }
                }
''',
        "notification when on-device pairing PIN arrives",
    )
    return source


def patch_host(source: str) -> str:
    if MARK in source:
        requirements = ("scarletV182PairingStatusPoll",
                        "scarletV182CodeFocus",
                        "Continue to Apple ID and 2FA",
                        "UNUserNotificationCenter.current()")
        if any(term not in source for term in requirements):
            raise ValueError("P00 incomplete host onboarding patch")
        return source
    for term in ("SCARLET_V167_ORIGINAL_ONDEVICE_PAIR_RESTORE",
                 "SCARLET_V170_PAIR_COMMAND_CONTEXT",
                 "struct V3PairingView: View",
                 "struct V3PromptSection: View"):
        if term not in source:
            raise ValueError("P00 host not prepared: " + term)

    if "import UserNotifications" not in source:
        source = once(source, "import SwiftUI\n", "import SwiftUI\nimport UserNotifications\n",
                      "user notification import")

    # The native pairing button explicitly requests user consent before the
    # service starts, but denial never blocks pairing.
    source = once(
        source,
        '''        if operation == "wirelessPairStart" {
            NSLog("[SCARLET_V167_ONDEVICE_UI] action=start")
        }
''',
        '''        if operation == "wirelessPairStart" {
            // SCARLET_V182_P00_PAIRING: explicit, user-triggered request.
            // Notification authorization is not a pairing precondition.
            _ = try? await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound])
            NSLog("[SCARLET_V167_ONDEVICE_UI] action=start")
        }
''',
        "request notification consent only on explicit pairing action",
    )

    # Automatically re-check transient pairing state while this view is in the
    # foreground, so the six-digit PIN is displayed without manual Refresh.
    source = once(
        source,
        '''        .onChange(of: nativePairScenePhase) { phase in
            if phase == .active {
                Task { await onDevicePairCommand("wirelessPairStatus") }
            }
        }
''',
        '''        .task(id: onDevicePairPhase) {
            // scarletV182PairingStatusPoll: SwiftUI cancels on view removal
            // or state change. No background polling or unattended pairing.
            guard onDevicePairPhase == "waiting" ||
                  onDevicePairPhase == "pin" else { return }
            for _ in 0..<90 {
                guard !Task.isCancelled else { return }
                try? await Task.sleep(nanoseconds: 1_000_000_000)
                guard !Task.isCancelled else { return }
                if nativePairScenePhase == .active {
                    await onDevicePairCommand("wirelessPairStatus")
                }
                guard onDevicePairPhase == "waiting" ||
                      onDevicePairPhase == "pin" else { return }
            }
        }
        .onChange(of: nativePairScenePhase) { phase in
            if phase == .active {
                Task { await onDevicePairCommand("wirelessPairStatus") }
            }
        }
''',
        "automatic foreground pairing-code refresh",
    )

    # The same setup surface links to the existing Apple ID & 2FA handler;
    # no standalone SideStore UI, guest overlay or second auth implementation.
    source = once(
        source,
        '''                if !onDevicePairDetail.isEmpty {
                    Text(onDevicePairDetail).font(.caption).foregroundColor(.secondary)
                }
            }
''',
        '''                if onDevicePairPhase == "complete" || pairingState == .satisfied {
                    NavigationLink {
                        V3SignInView().environmentObject(status)
                    } label: {
                        Label("Continue to Apple ID and 2FA", systemImage: "person.badge.key")
                    }
                }
                if !onDevicePairDetail.isEmpty {
                    Text(onDevicePairDetail).font(.caption).foregroundColor(.secondary)
                }
            }
''',
        "pairing-first next action",
    )

    # The trusted-device 2FA code is provided by Apple, never generated by
    # this pairing view. Keep and focus the existing oneTimeCode UITextField.
    source = once(
        source,
        '''    @State private var copiedDetails = false
    @State private var repairURL: URL?
''',
        '''    @State private var copiedDetails = false
    @State private var repairURL: URL?
    @FocusState private var scarletV182CodeFocus: Bool
''',
        "2FA focus state",
    )
    source = once(
        source,
        '''                    TextField("Verification code", text: binding("code"))
                        .keyboardType(.numberPad)
                        .textFieldStyle(.roundedBorder)
                        .textContentType(.oneTimeCode)
''',
        '''                    TextField("Verification code", text: binding("code"))
                        .keyboardType(.numberPad)
                        .textFieldStyle(.roundedBorder)
                        .textContentType(.oneTimeCode)
                        .focused($scarletV182CodeFocus)
                        .onAppear { scarletV182CodeFocus = true }
''',
        "focus the existing 2FA code field immediately",
    )
    return source


def apply(host_root: Path, side_root: Path) -> None:
    files = ((host_root / HOST, patch_host),
             (side_root / SERVICE, patch_service))
    prepared = []
    for path, transform in files:
        if not path.is_file() or path.is_symlink():
            raise ValueError("P00 source missing: " + str(path))
        before = path.read_text(encoding="utf-8")
        after = transform(before)
        if transform(after) != after:
            raise ValueError("P00 patch not idempotent: " + str(path))
        prepared.append((path, before, after))
    for path, before, after in prepared:
        if after != before:
            path.write_text(after, encoding="utf-8")
    print("[P00] On-device pairing notification+live code presentation+Apple 2FA focus integrated")
    print("[P00] Liquid Glass and existing dock/geometry files untouched")
    print("[UNVERIFIED] iPhone notification entitlement, Apple 2FA delivery and pairing handshake")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: patch_v182_p00_ondevice_pairing.py <LiveContainer> <SideStore>")
    apply(Path(sys.argv[1]), Path(sys.argv[2]))
