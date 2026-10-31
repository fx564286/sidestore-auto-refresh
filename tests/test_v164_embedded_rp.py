"""No V164 release unless new transport is in the embedded binary."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from verify_v164_embedded_rp import REQUIRED,verify

class V164EmbeddedTests(unittest.TestCase):
    def test_all_markers_required(self):
        binary=b'\xcf\xfa\xed\xfe'+b'\0'.join(REQUIRED)
        self.assertTrue(verify(binary))
        for missed in REQUIRED:
            with self.subTest(missed=missed),self.assertRaisesRegex(ValueError,'V164 compiled'):
                verify(b'\xcf\xfa\xed\xfe'+b'\0'.join(x for x in REQUIRED if x!=missed))
    def test_executable_must_be_macho(self):
        with self.assertRaisesRegex(ValueError,'Mach-O'):
            verify(b''.join(REQUIRED))
if __name__=='__main__':unittest.main()
