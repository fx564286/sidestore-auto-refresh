"""V165 runtime setup UI + old V163 glass markers remain mandatory."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
try:
    from tests.test_v163_package_parity import BASE,CURRENT,BOOT,MARKERS,V161,MARKER,NEW
except ModuleNotFoundError as e:
    if e.name!='tests':raise
    from test_v163_package_parity import BASE,CURRENT,BOOT,MARKERS,V161,MARKER,NEW
from package_livecontainer_combined import verify_versioned_picker_markers
V165=b'[SCARLET_V165_FIRST_INSTALL] action=reload_confirmed'
class V165BinaryContract(unittest.TestCase):
    def test_inherited_control_markers(self):
        verify_versioned_picker_markers('3.8.238',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,NEW,V165)),BOOT)
    def test_missing_v165_marker(self):
        with self.assertRaisesRegex(ValueError,'V165 compiled'):
            verify_versioned_picker_markers('3.8.238',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,NEW)),BOOT)
    def test_missing_native_button_marker(self):
        with self.assertRaisesRegex(ValueError,'V163 compiled'):
            verify_versioned_picker_markers('3.8.238',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,V165)),BOOT)
if __name__=='__main__':unittest.main()
