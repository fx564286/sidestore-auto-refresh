"""P61: Restore missing SideStore-managed active/inactive sideload functionality."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = (ROOT / 'integration/ScarletDeviceInstallAgent.swift.txt').read_text()
WIRE = (ROOT / 'integration/wire_scarlet_auth.py').read_text()
SUPPORT = (ROOT / 'HostApp/ScarletAuthXPCSupport.swift').read_text()
HOST = (ROOT / 'HostApp/ScarletIntegratedHostView.swift').read_text()
WORKFLOW = (ROOT.parent / '.github/workflows/scarlet-paired-engines-build.yml').read_text()

class NativeSideloadSlotContract(unittest.TestCase):
    def test_actual_upstream_deactivation_and_reactivation_pipelines_not_fake_defaults(self):
        for marker in (
            'AppManager.shared.deactivate(app, presentingViewController: nil)',
            'AppManager.shared.activate(app, presentingViewController: nil)',
            'InstalledApp.all(in: context)',
            'try await DatabaseManager.shared.start()',
            '$0.resignedBundleIdentifier == bundle',
            'AppManager.shared.appsToDeactivate(for: app) != nil',
            'reply(false, "active_slot_full")',
        ): self.assertIn(marker, WORKER)
        self.assertNotIn('FileManager.default.removeItem(at: app', WORKER)
        self.assertNotIn('activeApp.isActive = false', WORKER)
        self.assertNotIn('AppManager.shared.deleteApp(', WORKER)
    def test_host_protected_and_immutable_unknown_targets(self):
        for marker in (
            'app.resignedBundleIdentifier != Bundle.Info.activeBundleIdentifier',
            'app.bundleIdentifier != StoreApp.altstoreAppID',
            'matches.count == 1',
            'reply(false, "host_protected")',
            'reply(false, "app_not_managed")',
            'bundle.allSatisfy',
        ): self.assertIn(marker, WORKER)
    def test_no_silent_app_deactivation_and_explicit_confirmation(self):
        self.assertIn('showingConfirmation = true', HOST)
        self.assertIn('.confirmationDialog(', HOST)
        self.assertIn('Button(pendingActive ? "재활성화" : "데이터 백업 후 비활성화"', HOST)
        self.assertIn('guard let bundle = pendingBundle else { return }', HOST)
        self.assertIn('Task { await change(bundle, active: target) }', HOST)
        self.assertIn('SideStore 원본 백업·복원 경로만 사용합니다', HOST)
        self.assertNotIn('AppManager.shared.deactivate(', HOST)
    def test_keep_guest_independent_from_device_install_and_privacy(self):
        self.assertIn('기기에 직접 설치한 앱만 관리합니다. 컨테이너 게스트 앱은 제한 대상이 아닙니다', HOST)
        self.assertIn('SCARLET_NATIVE_SLOT_MANAGER_SHEET', HOST)
        self.assertIn('SCARLET_NATIVE_SLOT_MANAGER_OPEN', HOST)
        self.assertIn('slot_management_inspected', HOST)
        self.assertIn('slot_operation_returned', HOST)
        self.assertIn('"device_verified": "false"', HOST)
        self.assertNotIn('"bundle_id": bundle', HOST)
    def test_real_lc_sidestore_xpc_and_watchdogs(self):
        for marker in (
            'scarletManagedSlots:', 'scarletSetManagedSlot:',
            'listManagedSlots:', 'setManagedSlot:reply:',
            'scarletManagedSlots { json, reason in',
            'scarletSetManagedSlot(bundleID, active: active)',
            'DispatchQueue.main.asyncAfter(deadline: .now() + 20)',
            'DispatchQueue.main.asyncAfter(deadline: .now() + 240)',
        ): self.assertIn(marker, WIRE + SUPPORT)
        self.assertIn('ScarletSlotOperationGate.shared.claim()', WORKER)
        self.assertIn('ScarletSlotsListGate', SUPPORT)
        self.assertIn('ScarletSlotChangeGate', SUPPORT)
        self.assertEqual(SUPPORT.count('CheckedContinuation<(apps: [ScarletSideloadSlot], reason: String), Never>'), 2)
    def test_fail_closed_on_unknown_stage_and_keep_device_unverified(self):
        for marker in (
            '"database_unavailable"', '"backup_or_deactivation_failed"',
            '"activation_or_restore_failed"',
            '"coredata_state_unverified"',
            '"side_store_pipeline_returned_device_unverified"',
        ): self.assertIn(marker, WORKER)
        self.assertIn('status = "처리 실패: " + result.1', HOST)
        self.assertIn('rows = after.apps', HOST)
    def test_separate_build_version_and_public_artifact(self):
        self.assertIn('fix/scarlet-v48-r6p61-slot-manager-20261114', WORKFLOW)
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.61)', WORKFLOW)
        self.assertIn('Scarlet-Crystal-V48-R6P61-SLOT-MANAGER-UNSIGNED.ipa', WORKFLOW)
        self.assertIn('scarlet-v48-r6p61-slot-manager-unsigned-20261114', WORKFLOW)
        self.assertIn('"3.8.61" if "r6p61"', WORKFLOW)

if __name__ == '__main__': unittest.main()
