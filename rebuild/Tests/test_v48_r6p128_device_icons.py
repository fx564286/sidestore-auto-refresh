"""R6P128: actual bundle identity artwork; no inferred IPA availability."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / "Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST = (ROOT / "HostApp/ScarletIntegratedHostView.swift").read_text()
WORKER = (ROOT / "integration/ScarletDeviceInstallAgent.swift.txt").read_text()

class DeviceIconsTests(unittest.TestCase):
    def test_device_artwork_is_forwarded_using_actual_bundle_identifier(self):
        tile = UI.split("private struct ScarletManagedDeviceLauncherTile:", 1)[1].split("private struct", 1)[0]
        self.assertIn("iconPNG: app.iconPNG", tile)
        self.assertIn("iconPNG: ScarletInstalledIconReader.icon(bundleID: slot.id)", HOST)
        self.assertIn("id: app.resignedBundleIdentifier", WORKER)
        self.assertIn("if let method = class_getClassMethod", HOST)

    def test_installation_is_not_ipa_availability_or_mutation_authority(self):
        sheet = HOST.split("private struct ScarletManagedSlotSheet:", 1)[1].split("// R6P61_SLOT_MANAGER_END", 1)[0]
        self.assertNotIn("원본 IPA 필요", sheet)
        self.assertIn("기기 설치 확인 · 관리 미등록", sheet)
        self.assertIn("app.editable && app.managed != false && app.id != Bundle.main.bundleIdentifier", sheet)
        self.assertIn("호스트 보호", sheet)
        self.assertIn("읽기 전용", sheet)

    def test_host_artwork_can_use_its_own_bundle_if_cache_is_unavailable(self):
        reader = HOST.split("private enum ScarletInstalledIconReader", 1)[1]
        self.assertIn("bundleID == Bundle.main.bundleIdentifier", reader)
        self.assertIn("CFBundlePrimaryIcon", reader)
        self.assertIn("UIImage(named:", reader)
        self.assertNotIn("sharedModel", reader)

if __name__ == "__main__":
    unittest.main()
