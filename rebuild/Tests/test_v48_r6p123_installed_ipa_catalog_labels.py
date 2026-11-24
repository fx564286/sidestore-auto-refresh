"""R6P123: managed IPA catalog must not project native install outcome."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
UI = (ROOT / 'Sources/ScarletIndependentUI/ScarletIndependentShell.swift').read_text()
HOST = (ROOT / 'HostApp/ScarletIntegratedHostView.swift').read_text()
WORKFLOW = (ROOT.parent / '.github/workflows/scarlet-paired-engines-build.yml').read_text()
BRANCH = 'fix/scarlet-v48-r6p123-device-install-labels-20261120'
ASSET = 'Scarlet-Crystal-V48-R6P123-DEVICE-INSTALL-LABELS-UNSIGNED.ipa'

class DeviceIPAInstallLabelContract(unittest.TestCase):
    def test_catalog_copy_does_not_assert_ipa_install_unverified(self):
        catalog = UI.split('"SCARLET_DEVICE_MANAGED_IPA_SECTION"', 1)[1].split('Text("LiveContainer 게스트")', 1)[0]
        self.assertNotIn('설치 미검증', catalog)
        self.assertNotIn('실제 iOS 설치 여부는 별도 확인', catalog)
        # R6P126 renders the same catalog in an independent launcher tile;
        # native record copy moved into its accessibilityValue, not guest flow.
        native_tile = UI.split('private struct ScarletManagedDeviceLauncherTile: View {', 1)[1].split(
            '@available(iOS 16.0, *)', 1)[0]
        self.assertIn('ScarletManagedDeviceLauncherTile(', catalog)
        for label in ('SideStore 관리 중', '비활성 관리 기록', '호스트 보호'):
            self.assertIn(label, native_tile)

    def test_catalog_event_records_registry_source_not_install_verdict(self):
        catalog = HOST.split('"sidestore", "device_app_catalog_loaded"', 1)[1].split('\n        }', 1)[0]
        self.assertIn('"selected_owner_managed_records"', catalog)
        self.assertIn('"installation_proxy_and_managed_records"', catalog)
        self.assertNotIn('"installation_verified"', catalog)
        self.assertIn('"installation_verified": "false"', (ROOT / 'HostApp/ScarletAutomaticRenewal.swift').read_text())

    def test_native_release_has_separate_r6p123_identity(self):
        self.assertIn(BRANCH, WORKFLOW)
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.123)', WORKFLOW)
        self.assertEqual(WORKFLOW.count(ASSET), 2)
        self.assertIn('scarlet-v48-r6p123-device-install-labels-unsigned-20261120', WORKFLOW)
        self.assertIn('if "r6p123" in __import__("os").environ.get("GITHUB_REF", ""): version="3.8.123"', WORKFLOW)

if __name__ == '__main__':
    unittest.main()
