from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
def read(p): return (ROOT/p).read_text()
class DeviceInventoryContract(unittest.TestCase):
    def test_lookup_is_real_read_only(self):
        gateway=read('integration/scarlet_device_inventory.py')
        self.assertIn('installation_proxy_get_apps(client, $0, nil, 0', gateway)
        self.assertIn('"Command": "Lookup"', gateway)
        self.assertIn('"ApplicationType": "User"', gateway)
        self.assertIn('get-task-allow', gateway)
        self.assertIn('self.safeFreePlist(nodes[i])', gateway)
        self.assertNotIn('installation_proxy_uninstall', gateway)
        self.assertIn('patch_device_inventory(engine)',read('integration/wire_scarlet_auth.py'))
    def test_unmanaged_device_apps_cannot_be_modified(self):
        worker=read('integration/ScarletDeviceInstallAgent.swift.txt')
        listing=worker.split('static func listManagedSlots(',1)[1].split('@objc(setManagedSlot:',1)[0]
        self.assertIn('minimuxer.gateway.scarletDeviceInventory()',listing)
        self.assertIn('managed: false, deviceInstalled: true',listing)
        self.assertIn('active: true, editable: false',listing)
        self.assertIn('current.teamID == owner.teamID',listing)
        self.assertIn('ready_inventory_unavailable',listing)
        mutation=worker.split('@objc(setManagedSlot:',1)[1]
        self.assertIn('selected_account_app_mismatch',mutation)
        self.assertIn('app_not_managed',mutation)
    def test_unverified_inventory_is_not_empty_success(self):
        self.assertIn('ready_inventory_unavailable',read('HostApp/ScarletAuthXPCSupport.swift'))
        self.assertIn('실제 기기 조회 불가 · 관리 기록만 표시',read('Sources/ScarletIndependentUI/ScarletIndependentShell.swift'))
    def test_distinct_build_identity(self):
        wf=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.127)',wf)
        self.assertEqual(wf.count('Scarlet-Crystal-V48-R6P127-DEVICE-INVENTORY-RENEWAL-UNSIGNED.ipa'),2)
if __name__=='__main__': unittest.main()
