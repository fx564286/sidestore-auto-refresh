"""Host buttons and panel remain byte-marker compatible with V163 in V164."""
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
class V164UnchangedUI(unittest.TestCase):
    def test_v163_panel_native_buttons_still_required(self):
        verify_versioned_picker_markers('3.8.237',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,NEW)),BOOT)
    def test_absent_button_marker_fails(self):
        with self.assertRaisesRegex(ValueError,'V163 compiled'):
            verify_versioned_picker_markers('3.8.237',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,)),BOOT)
if __name__=='__main__':unittest.main()
