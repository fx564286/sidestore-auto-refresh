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
check_virtual=mod.verify_v107_virtual_guest_control_binary

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
        for old in (b'LCDirectReturnPresenter', b'LCDirectReturnControl'):
            with self.assertRaisesRegex(ValueError,'obsolete'):
                check(markers+b' '+old)
class VirtualOwnerBinaryTests(unittest.TestCase):
    def test_virtual_owner_survives_compilation(self):
        check_virtual(b'scarlet.v103.virtual.guest.control')

    def test_required_virtual_owner_missing(self):
        with self.assertRaisesRegex(ValueError, "virtual guest control missing"):
            check_virtual(b"random compiled bytes")

    def test_obsolete_native_class_and_selector_are_rejected(self):
        marker=b'scarlet.v103.virtual.guest.control'
        for symbol in (b'LCReturnControl\x00', b'lcReturnControl\x00',
                       b'lcReturnToHost\x00'):
            with self.subTest(symbol=symbol):
                with self.assertRaisesRegex(ValueError, 'obsolete native'):
                    check_virtual(marker+b"\x00"+symbol)

    def test_preference_key_is_not_a_removed_class_symbol(self):
        check_virtual(b'scarlet.v103.virtual.guest.control\x00LCReturnControlPosition\x00')


if __name__=='__main__':unittest.main()
