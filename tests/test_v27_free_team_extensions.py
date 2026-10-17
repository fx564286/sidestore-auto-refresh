"""V27 new fresh-app install on a free team: optional extensions remain scoped."""
import tempfile
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/patch_v27_free_team_extensions.py"
MARK = "NRG_V27_FREE_TEAM_EXTENSIONS"

class FreeTeamExtensionsTest(unittest.TestCase):
    def test_patcher_targets_only_fresh_free_team_installs(self):
        s = SOURCE.read_text()
        for val in ("team.type == .free", "localAppExtensions == nil",
                    "!UserDefaults.standard.customizeAppExtensions",
                    "try self.removeExtensions(from: targetAppBundle.appExtensions, endPercent: 85)",
                    "try self.updateManifest()", "return targetAppBundle"):
            self.assertIn(val,s)
        self.assertNotIn("ideviceinstaller uninstall",s)
        self.assertNotIn("removeItem(at: installed",s)

    def test_embedded_source_idempotence(self):
        spec = importlib.util.spec_from_file_location("v27_ext_patch",str(SOURCE))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        path = ("SideStore/Core/Operations/PipelineOperations/"
                "RemoveAppExtensionsOperation.swift")
        # Minimal pinned fixture, intentionally contains existing manifest call.
        sample = """class Fake {
        func action() {
        self.setProgress(30)
        let excessExtensions = processExtensionsInfo(from: targetAppBundle, localAppExtensions: localAppExtensions)
        try self.updateManifest()
        }
}"""
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/path;p.parent.mkdir(parents=True);p.write_text(sample)
            module.patch(Path(d))
            output=p.read_text()
            self.assertEqual(output.count(MARK),1)
            self.assertEqual(output.count("try self.updateManifest()"),2)
            module.patch(Path(d))
            self.assertEqual(output,p.read_text())

    def test_runtime_files_still_keep_explicit_customization(self):
        code = (ROOT/"scripts/templates/v3_headless_runtime.swift").read_text()
        self.assertIn("NRG_V26_CANCEL_ORIGIN",code)
        self.assertIn('["install", "installURL", "installSharedIPA", "update"]',code)

if __name__=="__main__": unittest.main()
