"""Require V160 outside event + adaptive contrast in the real Swift binary."""
import unittest
try:
    from tests.test_v159_package_parity import BASE, CURRENT, BOOT
except ModuleNotFoundError as exc:
    if exc.name != 'tests':
        raise
    from test_v159_package_parity import BASE, CURRENT, BOOT
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from package_livecontainer_combined import verify_versioned_picker_markers

MARKERS = (b'[SCARLET_V160_OUTSIDE_RETURN] phase=outside_down',
           b'[SCARLET_V160_GUEST_WINDOW_COORDS] outside=',
           b'[SCARLET_V160_GLASS_CONTRAST] mode=adaptive')


class V160BinaryGates(unittest.TestCase):
    def test_compiled_v160_required(self):
        verify_versioned_picker_markers('3.8.233', BASE + b'\0'.join(CURRENT + MARKERS), BOOT)

    def test_missing_each_new_marker_rejected(self):
        for absent in MARKERS:
            remaining = tuple(x for x in MARKERS if x != absent)
            with self.subTest(absent=absent), self.assertRaisesRegex(ValueError, 'V160 compiled'):
                verify_versioned_picker_markers('3.8.233', BASE + b'\0'.join(CURRENT + remaining), BOOT)


if __name__ == '__main__':
    unittest.main()
