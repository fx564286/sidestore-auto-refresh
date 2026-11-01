"""V166 compiled Apple host has actual auto-import marker + legacy UI."""
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
V166=b'[SCARLET_V166_AUTOMATIC_RP_HANDOFF] phase=import_requested keys=redacted'
class V166BinaryTests(unittest.TestCase):
    def test_compiled_auto_import_and_old_controls(self):
        verify_versioned_picker_markers('3.8.239',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,NEW,V165,V166)),BOOT)
    def test_missing_auto_import_rejected(self):
        with self.assertRaisesRegex(ValueError,'V166 compiled'):
            verify_versioned_picker_markers('3.8.239',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,NEW,V165)),BOOT)
    def test_old_glass_still_required(self):
        with self.assertRaisesRegex(ValueError,'V163 compiled'):
            verify_versioned_picker_markers('3.8.239',BASE+b'\0'.join(CURRENT+MARKERS+V161+(MARKER,V165,V166)),BOOT)
if __name__=='__main__':unittest.main()
