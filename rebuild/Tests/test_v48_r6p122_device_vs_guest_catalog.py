"""R6P122: native device IPA catalog must never be presented as LC guest."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=(ROOT/"Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()

class DeviceVsGuestCatalog(unittest.TestCase):
    def test_two_independent_models_and_rows(self):
        self.assertIn("public struct ScarletManagedDevicePresentation",UI)
        self.assertIn("public let deviceApps: [ScarletManagedDevicePresentation]",UI)
        self.assertIn("ForEach(visibleDeviceApps) { app in",UI)
        self.assertIn("ForEach(visibleGuests) { guest in",UI)
        self.assertIn('SCARLET_DEVICE_MANAGED_IPA_SECTION',UI)
        self.assertIn('SCARLET_LC_GUEST_SECTION',UI)
        self.assertIn('실제 기기 설치 앱 및 관리 상태',UI)

    def test_device_listing_reuses_existing_native_authority(self):
        self.assertIn('await ScarletNativeSideloadSlots.list()',HOST)
        self.assertIn('deviceApps: managedDeviceApps',HOST)
        self.assertIn('deviceAppLookupStatus: deviceAppLookupStatus',HOST)
        self.assertIn('onManageDeviceApps: { showManagedSlotSheet = true }',HOST)
        self.assertNotIn('sharedModel.apps.map { app in\n            ScarletManagedDevicePresentation',HOST)

    def test_inventory_refreshes_when_account_and_install_state_change(self):
        self.assertIn('if raw == "앱"',HOST)
        self.assertIn('reloadManagedDeviceApps()',HOST)
        self.assertIn('deviceAppReadGeneration &+= 1',HOST)
        self.assertIn('guard generation == deviceAppReadGeneration else { return }',HOST)
        self.assertIn('deviceAppLookupStatus = "unavailable"',HOST)

    def test_release_build_branch_has_exact_unsigned_ipa_contract(self):
        workflow=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()
        branch="fix/scarlet-v48-r6p122-device-guest-catalog-20261120"
        self.assertIn(branch,workflow)
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.122)',workflow)
        self.assertIn('if "r6p122" in __import__("os").environ.get("GITHUB_REF", ""): version="3.8.122"',workflow)
        self.assertEqual(workflow.count('Scarlet-Crystal-V48-R6P122-DEVICE-GUEST-CATALOG-UNSIGNED.ipa'),2)
        self.assertIn('scarlet-v48-r6p122-device-guest-catalog-unsigned-20261120',workflow)

    def test_guest_uninstall_cannot_operate_on_native_rows(self):
        home=UI[UI.index('    private var home: some View {'):UI.index('    private var visibleGuests:')]
        self.assertIn('ScarletGuestLauncherTile(',home)
        self.assertIn('onDelete: { onDeleteGuest(guest.id) }',home)
        self.assertNotIn('onDeleteGuest(app.id)',home)
        self.assertNotIn('onOpenGuest(app.id)',home)

if __name__ == "__main__": unittest.main()
