"""Early SideStore startup must not force LCSharedUtils's cached group path."""
from pathlib import Path
import importlib.util
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "p00_defer_group", ROOT/"scripts/patch_v182_p00_defer_app_group_probe.py")
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class EarlyGroupProbeTests(unittest.TestCase):
    def test_original_hook_probe_is_replaced_once(self):
        original = '#import "LCSharedUtils.h"\nvoid installSideStoreHooks(void) {\n' + m.OLD + '\n}\n'
        fixed = m.patch(original)
        self.assertEqual(m.patch(fixed), fixed)
        self.assertIn("SCARLET_V182_P00_DEFER_EARLY_GROUP_PROBE", fixed)
        self.assertIn("group_probe=deferred", fixed)
        self.assertNotIn("LCSharedUtils.appGroupPath != nil", fixed)
        self.assertEqual(fixed.count("void installSideStoreHooks(void)"), 1)

    def test_missing_known_upstream_marker_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "anchor changed"):
            m.patch("void installSideStoreHooks(void) {}\n")

    def test_authoritative_runtime_app_group_remains_unmodified(self):
        # Only SideStoreHooks.m is changed. V3SharedAppGroup.runtimeIdentity()
        # remains the source of authoritative runtime App Group validation.
        assert m.REL.as_posix() == "SideStoreSupport/SideStoreHooks.m"
        builder = (ROOT/".github/workflows/scarlet-v181-design-auth-build.yml").read_text()
        self.assertIn("patch_v182_p00_defer_app_group_probe.py", builder)
        self.assertIn("patch_embedded_sidestore_startup.py", builder)
        self.assertLess(builder.index("patch_embedded_sidestore_startup.py"),
                        builder.index("patch_v182_p00_defer_app_group_probe.py"))


if __name__=="__main__":
    unittest.main()
