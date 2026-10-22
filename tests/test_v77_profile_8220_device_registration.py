import importlib.util
import unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'scripts/patch_v77_profile_8220_device_registration.py'
s=importlib.util.spec_from_file_location('v77',p)
m=importlib.util.module_from_spec(s)
s.loader.exec_module(m)
class ProfileDeviceTests(unittest.TestCase):
    def test_targeted_8220_and_idempotence(self):
        src='LC_PROVISIONING_PARENT_ID_UPSTREAM_V1\n'+m.ANCHOR
        out=m.patch(src)
        self.assertEqual(m.patch(out),out)
        self.assertIn('serverCode == 8220',out)
        self.assertIn('fetchUDID()',out)
        self.assertIn('fetchDevices(for: team, types: .all)',out)
        self.assertEqual(out.count('registerDevice('),1)
    def test_unknown_source_blocked(self):
        with self.assertRaises(ValueError):
            m.patch('unexpected source revision')
if __name__=='__main__': unittest.main()
