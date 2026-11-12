"""R6P15: guest-owned top safe area and bounded saved-pairing reconnect."""
import importlib.util
import tempfile
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOST = (ROOT / "HostApp/ScarletFullscreenSceneStack.swift").read_text()
REC = (ROOT / "HostApp/ScarletDiagnosticRecorder.swift").read_text()
WORKER = (ROOT / "integration/ScarletGuestRefreshAgent.swift.txt").read_text()
GUEST = (ROOT / "integration/ScarletGuestIslandContentGuard.m.txt").read_text()
INTEGRATION = (ROOT / "integration/apply_scarlet_host.py").read_text()


class GuestRootAndPairingRecovery(unittest.TestCase):
    def test_host_sends_normal_window_safe_top_not_transient_viewport_zero(self):
        area = HOST.split("private func captureSafeAreaSnapshot(", 1)[1].split(
            "    override func viewSafeAreaInsetsDidChange()", 1)[0]
        self.assertIn("let n = normal?.safeAreaInsets ?? .zero", area)
        self.assertIn("n.top >= 20, n.top <= 130", area)
        self.assertIn("Scarlet.Guest.PortraitSafeTop.V1", area)
        self.assertNotIn('LCUtils.appGroupUserDefault.set(Double(actual.top)', area)

    def test_guest_scoped_no_hooks_no_resize_and_no_app_exceptions(self):
        self.assertIn('boolForKey:@"Scarlet.ResidentSDKContract.V1"', GUEST)
        self.assertIn("NSUserDefaults.isLiveProcess", GUEST)
        self.assertIn("UIWindowDidBecomeVisibleNotification", GUEST)
        self.assertIn("UIWindowDidBecomeKeyNotification", GUEST)
        self.assertIn("root.additionalSafeAreaInsets = extra", GUEST)
        self.assertIn("CGFloat deficit = MIN(130, MAX(0, target - before));", GUEST)
        self.assertIn("guest_root_already_safe", GUEST)
        self.assertIn("objc_getAssociatedObject(", GUEST)
        self.assertIn("objc_setAssociatedObject(", GUEST)
        self.assertIn("guest_root_excess_trimmed", GUEST)
        self.assertIn("attempt < 2", GUEST)
        self.assertIn("if(ourDelta > 0)", GUEST)
        self.assertNotIn("method_exchangeImplementations", GUEST)
        self.assertNotIn("UIApplication.sharedApplication", GUEST.split("#import", 1)[1])
        self.assertNotIn(".frame =", GUEST)
        self.assertNotIn("spoofSDKVersion", GUEST)
        self.assertNotIn("com.instagram", GUEST)

    def test_generate_one_existing_tweak_initializer_without_hooking_others(self):
        spec = importlib.util.spec_from_file_location(
            "scarlet_apply_r6p15", ROOT / "integration/apply_scarlet_host.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            engine = Path(folder)
            tweaks = engine / "LiveContainer/Tweaks"
            tweaks.mkdir(parents=True)
            (tweaks / "Tweaks.h").write_text(
                "void initScarletGuestAudioIsolation(void);\n")
            bootstrap = engine / "LiveContainer/LCBootstrap.m"
            bootstrap.write_text(
                "        initScarletGuestAudioIsolation();\n")
            result = module.add_scarlet_guest_island_content_guard(engine)
            self.assertTrue(result["residentOnly"])
            self.assertFalse(result["windowResized"])
            self.assertFalse(result["globalUIKitHook"])
            generated = tweaks / "ScarletGuestIslandContentGuard.m"
            self.assertEqual(generated.read_text(), GUEST)
            self.assertIn("initScarletGuestIslandContentGuard(void);",
                          (tweaks / "Tweaks.h").read_text())
            self.assertIn("initScarletGuestIslandContentGuard();",
                          bootstrap.read_text())

    def test_guest_reports_actual_root_safearea_and_host_replays(self):
        self.assertIn("Scarlet.Guest.IslandRootReceipt.V1", GUEST)
        self.assertIn("com.scarlet.guest.island.ack.", GUEST)
        self.assertIn("guest_root_safearea_receipt", HOST)
        self.assertIn("ScarletGuestIslandReceiptObserver.shared.observe(pid: vc.pid)", HOST)
        self.assertIn('"guest_root_top_pt", "guest_root_after_pt"', REC)
        self.assertIn("guest_root_update_unconfirmed", HOST)

    def test_saved_pairing_retries_one_real_transport_probe(self):
        part = WORKER.split("@objc static func inspectDevicePairing(", 1)[1].split(
            "// V29: in-app iOS 27 RPPairing", 1)[0]
        self.assertEqual(part.count("try await ScarletGuestDeviceTransport.ensureReady()"), 2)
        self.assertIn("Task.sleep(nanoseconds: 1_100_000_000)", part)
        self.assertIn('reply(false, "pairing_saved_transport_unavailable")', part)
        self.assertIn('reply(true, "pairing_saved_and_transport_ready")', part)
        self.assertNotIn("savePairingFile(", part)
        self.assertNotIn("removePairingFile", part)


if __name__ == "__main__":
    unittest.main()
