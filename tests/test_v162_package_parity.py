"""Compiled V162 identification while retaining V161 binary gate."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    from tests.test_v161_package_parity import BASE,CURRENT,BOOT,MARKERS,V161
except ModuleNotFoundError as e:
    if e.name!='tests':raise
    from test_v161_package_parity import BASE,CURRENT,BOOT,MARKERS,V161
from package_livecontainer_combined import verify_versioned_picker_markers
MARKER=b'[SCARLET_V162_SIXTH_SMALLER] panel='
class V162PackageTests(unittest.TestCase):
    def test_new_marker_and_prior_gates(self):
        verify_versioned_picker_markers('3.8.235',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,)),BOOT)
    def test_missing_marker_rejected(self):
        with self.assertRaisesRegex(ValueError,'V162 compiled'):
            verify_versioned_picker_markers('3.8.235',BASE+b'\0'.join(CURRENT+MARKERS+V161),BOOT)
if __name__=='__main__':unittest.main()
