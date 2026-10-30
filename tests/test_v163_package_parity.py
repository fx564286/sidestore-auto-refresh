"""V163 compiled marker gate and inherited V162 runtime functionality."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    from tests.test_v162_package_parity import BASE, CURRENT, BOOT, MARKERS, V161, MARKER
except ModuleNotFoundError as exc:
    if exc.name != 'tests': raise
    from test_v162_package_parity import BASE, CURRENT, BOOT, MARKERS, V161, MARKER
from package_livecontainer_combined import verify_versioned_picker_markers
NEW=b'[SCARLET_V163_BUTTON_FOOTPRINT] width_delta=14 native_only=1'
class V163BinaryGate(unittest.TestCase):
    def test_combined_v163_markers(self):
        verify_versioned_picker_markers('3.8.236',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,NEW)),BOOT)
    def test_missing_new_marker_fails(self):
        with self.assertRaisesRegex(ValueError,'V163 compiled'):
            verify_versioned_picker_markers('3.8.236',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,)),BOOT)
if __name__=='__main__':unittest.main()
