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
check=mod.verify_guest_return_control_binary_markers
collapsed=b'[LC_RETURN] CONTROL_COLLAPSED'
old=b'[LC_RETURN] CONTROL_RESTORED'
new=b'[SCARLET_V103_CONTROL] restored_and_dispatched=1'

class GuestControlBinaryTests(unittest.TestCase):
    def test_legacy_valid(self):
        self.assertEqual(check(collapsed+old,collapsed+old),'legacy-restored')

    def test_v103_valid_without_retired_marker(self):
        self.assertEqual(check(collapsed+new,collapsed),'v103-single-control')
        self.assertEqual(check(collapsed,collapsed+new),'v103-single-control')

    def test_missing_collapse_rejected_in_either_library(self):
        for first,second in ((old,collapsed+new),(collapsed+new,b'')):
            with self.subTest(first=first,second=second):
                with self.assertRaisesRegex(ValueError,'collapsible guest control missing'):
                    check(first,second)

    def test_missing_restoration_rejected(self):
        with self.assertRaisesRegex(ValueError,'neither legacy nor V103'):
            check(collapsed,collapsed)

    def test_stale_legacy_half_build_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'neither legacy nor V103'):
            check(collapsed+old,collapsed)

if __name__=='__main__':unittest.main()
