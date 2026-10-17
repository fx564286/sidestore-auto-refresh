import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MOD_PATH = ROOT / "scripts/patch_v28_refresh_regression.py"

class V28RefreshCompatibility(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("v28", MOD_PATH)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)

    def test_v26_refresh_path_restored_without_changing_new_install(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / self.mod.PATH
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("""// NRG_V27_PROFILE_CAPACITY_PREFLIGHT
// NRG_V27_FREE_TEAM_SERIAL_PROVISIONING
        if team.type == .free {
            let ordered = targetAppBundle.appExtensions.sorted
        }
        guard team.type == .free else { return }
        let existing: [ALTAppID]
""")
            self.mod.patch(Path(d))
            s = target.read_text()
            self.assertEqual(s.count(self.mod.MARKER), 2)
            self.assertIn("team.type == .free && self.context.installedApp == nil", s)
            self.assertIn("guard team.type == .free && self.context.installedApp == nil else { return }", s)
            self.assertIn("let ordered = targetAppBundle.appExtensions.sorted", s)
            self.mod.patch(Path(d))
            self.assertEqual(s, target.read_text())

    def test_fail_closed_for_unknown_v27_anchor(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / self.mod.PATH
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("NO_V27_SOURCE")
            with self.assertRaises(ValueError):
                self.mod.patch(Path(d))
            self.assertEqual(target.read_text(), "NO_V27_SOURCE")

if __name__ == "__main__":
    unittest.main()
