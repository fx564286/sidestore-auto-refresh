"""The P106 renewal outcome allowlist is compiled into SideStoreSupport, not LC UI."""
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[2]
CI = (ROOT / '.github/workflows/scarlet-paired-engines-build.yml').read_text()
WIRE = (ROOT / 'rebuild/integration/wire_scarlet_auth.py').read_text()
XPC = (ROOT / 'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()
SIDE = (ROOT / 'rebuild/integration/ScarletGuestRefreshAgent.swift.txt').read_text()

class P106BinaryOwnership(unittest.TestCase):
    def test_native_xpc_allowlist_compiled_owner(self):
        self.assertIn('engine / "SideStoreSupport/ScarletAuthXPCSupport.swift"', WIRE)
        self.assertIn('"native_host_reinstall_returned_install_unverified"', XPC)
        self.assertIn('"native_host_reinstall_owner_unverified"', XPC)
        self.assertIn('assert b"native_host_reinstall_returned_install_unverified" in xpc_bin', CI)
        self.assertNotIn('assert b"native_host_reinstall_returned_install_unverified" in host_bin', CI)
    def test_native_worker_outcome_remains_original_installer(self):
        self.assertIn('AppManager.shared.install(.url(installedHost)', SIDE)
        self.assertIn('reply(true, "native_host_reinstall_returned_install_unverified")', SIDE)
        self.assertIn('assert b"native_host_reinstall_returned_install_unverified" in side_bin', CI)

if __name__ == '__main__':
    unittest.main()
