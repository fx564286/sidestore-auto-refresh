import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "verify_scarlet_design", ROOT / "scripts/verify_scarlet_design.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
CONTRACT = json.loads((ROOT / "config/scarlet-ui-preservation.json").read_text())

class ScarletDesignTests(unittest.TestCase):
    def test_stock_livecontainer_does_not_qualify_as_user_design(self):
        with tempfile.TemporaryDirectory() as d:
            r=module.check(Path(d), CONTRACT)
            self.assertFalse(r["user_authored_design_source_preserved"])
            self.assertFalse(r["can_publish_as_design_preserved"])
            self.assertFalse(r["runtime_design_verified"])

    def test_missing_single_element_blocks_complete_release(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            files={}
            for item in CONTRACT["requirements"]:
                files.setdefault(item["path"], set()).update(item["all"])
            for file, markers in files.items():
                target=root/file
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_text("\n".join(sorted(markers)))
            self.assertTrue(module.check(root,CONTRACT)["user_authored_design_source_preserved"])
            panel=root/"MultitaskSupport/MultitaskDockView.swift"
            panel.write_text(panel.read_text().replace("SCARLET_V160_OUTSIDE_RETURN",""))
            r=module.check(root,CONTRACT)
            self.assertFalse(r["can_publish_as_design_preserved"])
            self.assertIn("outside_tap",[x["feature"] for x in r["checks"] if not x["pass"]])

    def test_no_source_escape(self):
        with tempfile.TemporaryDirectory() as d:
            contract=json.loads(json.dumps(CONTRACT))
            contract["requirements"][0]["path"]="../secret"
            with self.assertRaisesRegex(ValueError,"unsafe source path"):
                module.check(Path(d),contract)

if __name__ == "__main__":
    unittest.main()
