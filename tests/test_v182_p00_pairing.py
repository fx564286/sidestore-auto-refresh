"""P00 pairing/2FA checks against the actual generated host and SideStore adapters.

These are source-level tests only. They do not claim iPhone notification
authorization, a verified wireless handshake, Apple account delivery or refresh.
"""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]

def module_from_script(name: str, script: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

m = module_from_script("scarlet_p00_pairing", "patch_v182_p00_ondevice_pairing.py")
v167 = module_from_script("scarlet_v167_pairing", "patch_v167_restore_ondevice_pairing.py")


def host_fixture():
    return (
        "import SwiftUI\n"
        "// SCARLET_V170_PAIR_COMMAND_CONTEXT\n"
        "struct V3PairingView: View {\n"
        "    @State private var onDevicePairPhase = \"idle\"\n"
        + v167.UI +
        '''
        .onChange(of: nativePairScenePhase) { phase in
            if phase == .active {
                Task { await onDevicePairCommand("wirelessPairStatus") }
            }
        }
        if operation == "wirelessPairStart" {
            NSLog("[SCARLET_V167_ONDEVICE_UI] action=start")
        }
'''
        + """
    private func onDevicePairCommand(_ operation: String) async {}
}
struct V3PromptSection: View {
    @State private var copiedDetails = false
    @State private var repairURL: URL?
"""
        + '''
                    TextField("Verification code", text: binding("code"))
                        .keyboardType(.numberPad)
                        .textFieldStyle(.roundedBorder)
                        .textContentType(.oneTimeCode)
'''
        + "\n}\n"
        + "let liquidGlassContractMarker = \"SCARLET_V144_GLASS_INSTALLED\"\n"
    )


def service_fixture():
    return '''import UserNotifications
// SCARLET_V167_ORIGINAL_ONDEVICE_PAIR_RESTORE
@MainActor
final class V3OriginalOnDevicePairingSession {
    private var stagedURL: URL?

    func status() -> [String: Any] { [:] }

    func begin() {
        phase = "waiting"
        pin = ""
        // Called by WirelessPairService
                self.detail = "Enter the displayed code in iOS Settings"
    }
}
'''


class P00PairingRegressions(unittest.TestCase):
    def test_pairing_host_is_idempotent_and_glass_marker_preserved(self):
        source = host_fixture()
        result = m.patch_host(source)
        self.assertEqual(m.patch_host(result), result)
        self.assertEqual(result.count("SCARLET_V144_GLASS_INSTALLED"),
                         source.count("SCARLET_V144_GLASS_INSTALLED"))
        self.assertIn("scarletV182PairingStatusPoll", result)
        self.assertIn("onDevicePairPhase == \"waiting\"", result)
        self.assertIn("onDevicePairPhase == \"pin\"", result)
        self.assertIn("nativePairScenePhase == .active", result)
        self.assertIn("Continue to Apple ID and 2FA", result)
        self.assertIn("V3SignInView().environmentObject(status)", result)
        self.assertIn("scarletV182CodeFocus = true", result)
        self.assertIn(".textContentType(.oneTimeCode)", result)

    def test_pin_notification_is_bounded_and_consent_driven(self):
        source = service_fixture()
        result = m.patch_service(source)
        self.assertEqual(m.patch_service(result), result)
        self.assertIn("WirelessPairService", result)
        self.assertIn("self.lastNotifiedPairingPIN != pairingPIN", result)
        self.assertIn("pairingPIN.utf8.count == 6", result)
        self.assertIn("authorizationStatus == .authorized", result)
        self.assertIn("authorizationStatus == .provisional", result)
        self.assertIn("UNNotificationRequest(", result)
        self.assertIn("trigger: UNTimeIntervalNotificationTrigger(", result)
        self.assertNotIn("NSUserDefaults.standard.set(pairingPIN", result)
        self.assertNotIn('NSLog("%@", pairingPIN)', result)

    def test_missing_wireless_pairing_contract_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "WirelessPair bridge"):
            m.patch_service("import UserNotifications\n")
        with self.assertRaisesRegex(ValueError, "host not prepared"):
            m.patch_host("import SwiftUI\n")

    def test_refresh_remains_an_independent_p00_path(self):
        shell = (ROOT / "scripts/templates/v3_unified_shell.swift").read_text()
        policy = (ROOT / "scripts/templates/v3_behavioral_primitives.swift").read_text()
        self.assertIn("V3RefreshPrerequisite.evaluate(", shell)
        self.assertIn('Notification.Name("LiveContainerAutoRefreshRunNow")', shell)
        self.assertIn("V3RefreshAllTerminalEvidencePolicy", policy)
        self.assertIn('"pairingImportData"', policy)
        port = (ROOT / "scripts/port_v180_design.py").read_text()
        self.assertIn('patch_v182_p00_ondevice_pairing.py', port)


if __name__ == "__main__":
    unittest.main()
