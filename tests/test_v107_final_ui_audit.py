"""V107 generated guest control ownership audit, independently tested."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / (name+".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

v105 = load("patch_v105_delete_legacy_return")
fixture_spec = importlib.util.spec_from_file_location("v105_fixture",
    ROOT / "tests/test_v105_delete_legacy_return.py")
fixture_module = importlib.util.module_from_spec(fixture_spec)
fixture_spec.loader.exec_module(fixture_module)
audit = load("audit_v107_active_guest_ui")
settings_module = load("patch_v107_retire_dead_return_settings")
settings_fixture_spec = importlib.util.spec_from_file_location(
    "v107_settings_fixture", ROOT / "tests/test_v107_retire_dead_return_settings.py")
settings_fixture = importlib.util.module_from_spec(settings_fixture_spec)
settings_fixture_spec.loader.exec_module(settings_fixture)


class V107FinalUIAuditTests(unittest.TestCase):
    def fixtures(self, root):
        data = {
            audit.NATIVE: v105.native(fixture_module.NATIVE),
            audit.VIRTUAL: "SCARLET_V103_VIRTUAL_ONLY_CONTROL scarlet.v103.virtual.guest.control",
            audit.DOCK: "SCARLET_V103_IMMEDIATE_GUEST_SWITCH defer { dismissSelection() }",
            audit.DIRECT: v105.direct(fixture_module.DIRECT),
            audit.SETTINGS: settings_module.patch(settings_fixture.OLD),
        }
        for rel, content in data.items():
            p = root/rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        return data

    def test_one_direct_owner_and_virtual_host_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fixtures(Path(tmp))
            result = audit.inspect(Path(tmp))
            self.assertEqual(result["status"], "PASS", result["problems"])
            self.assertEqual(len(result["owners"]), 2)
            self.assertFalse(result["device_geometry_verified"])

    def test_old_label_or_obsolete_class_triggers_release_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixtures(root)
            p = root/audit.DIRECT
            for injection in ("홍수정", "@interface LCDirectReturnPresenter : NSObject"):
                with self.subTest(injection=injection):
                    original = p.read_text()
                    p.write_text(original+injection)
                    result = audit.inspect(root)
                    self.assertEqual(result["status"], "FAIL")
                    p.write_text(original)

    def test_old_settings_rows_are_release_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixtures(root)
            path = root/audit.SETTINGS
            path.write_text(path.read_text() + 'Toggle("Show Return Button"')
            self.assertEqual(audit.inspect(root)["status"], "FAIL")

    def test_missing_portrait_hit_target_and_old_virtual_control_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixtures(root)
            direct = root/audit.DIRECT
            direct.write_text(direct.read_text().replace("portraitUI ? 44 : 28", "28"))
            self.assertEqual(audit.inspect(root)["status"], "FAIL")
            self.fixtures(root)
            virt = root/audit.VIRTUAL
            virt.write_text(virt.read_text()+" nrgV72WindowOverflowLongPress:")
            self.assertEqual(audit.inspect(root)["status"], "FAIL")

if __name__ == '__main__':
    unittest.main()
