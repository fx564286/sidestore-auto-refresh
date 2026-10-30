"""V161 Swift-binary guard for blank panel + tab resize."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    from tests.test_v160_package_parity import BASE, CURRENT, BOOT, MARKERS
except ModuleNotFoundError as e:
    if e.name != 'tests':raise
    from test_v160_package_parity import BASE, CURRENT, BOOT, MARKERS
from package_livecontainer_combined import verify_versioned_picker_markers
V161=(b'[SCARLET_V161_BLANK_PANEL_DISMISS] phase=blank_accepted',
      b'[SCARLET_V161_RESIZE_TAB] list=')
class V161BinaryContract(unittest.TestCase):
    def test_required_markers(self):
        verify_versioned_picker_markers('3.8.234',BASE+b'\0'.join(CURRENT+MARKERS+V161),BOOT)
    def test_each_marker_rejected_when_absent(self):
        for missing in V161:
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError,'V161 compiled'):
                remaining=tuple(x for x in V161 if x!=missing)
                verify_versioned_picker_markers('3.8.234',BASE+b'\0'.join(CURRENT+MARKERS+remaining),BOOT)
if __name__=='__main__':unittest.main()
