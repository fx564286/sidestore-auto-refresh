"""Fail-closed Mach-O marker verification for V103 single-control packaging."""
import importlib.util
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec=importlib.util.spec_from_file_location('packager',ROOT/'scripts'/'package_livecontainer_combined.py')
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
check=mod.verify_v105_direct_morph_binary

class GuestControlBinaryTests(unittest.TestCase):
    def test_current_v105_morph_present(self):
        markers=b'SCGuestMorphPresenter scarlet.v105.direct.morph [SCARLET_V105_CONTROL]'
        self.assertIsNone(check(markers))
    def test_each_missing_owner_marker_fails(self):
        markers=(b'SCGuestMorphPresenter',b'scarlet.v105.direct.morph',
                 b'[SCARLET_V105_CONTROL]')
        for i in range(len(markers)):
            with self.subTest(i=i):
                with self.assertRaisesRegex(ValueError,'missing'):
                    check(b' '.join(v for j,v in enumerate(markers) if j!=i))
    def test_old_control_must_not_exist_even_if_new_present(self):
        markers=b'SCGuestMorphPresenter scarlet.v105.direct.morph [SCARLET_V105_CONTROL]'
        for old in (b'LCDirectReturnPresenter',b'LCDirectReturnControl'):
            with self.assertRaisesRegex(ValueError,'obsolete'):
                check(markers+b' '+old)
if __name__=='__main__':unittest.main()
