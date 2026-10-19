import tempfile
import shutil
import unittest
from pathlib import Path
from importlib.util import spec_from_file_location, module_from_spec

ROOT=Path(__file__).resolve().parents[1]
spec=spec_from_file_location('v57',ROOT/'scripts/patch_v57_ota_identity.py')
v57=module_from_spec(spec)
spec.loader.exec_module(v57)

class V57Tests(unittest.TestCase):
    def test_patch_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for relative in (v57.SHELL,v57.SERVICE):
                out=root/relative
                out.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/relative,out)
            v57.main(root)
            content=(root/v57.SHELL).read_text()
            self.assertIn('hostEntry.bundleID == signedHostID',content)
            self.assertIn('NRG_V59_OTA_EXTERNAL_INSTALL',content)
            self.assertIn('note = hostEntry == nil',content)
            self.assertNotIn('reason=installed_host_not_matched count=%d',content)
            self.assertIn('await status.reloadAndWait(manual: true)',content)
            self.assertIn('stage=self_identity',content)
            self.assertIn('Text("#\\(current)")',content)
            self.assertNotIn('Text("#\\\\(current)")',content)
            self.assertIn('Bundle.main.bundleIdentifier',(root/v57.SERVICE).read_text())
            v57.main(root)
            self.assertEqual(content,(root/v57.SHELL).read_text())

if __name__=='__main__':unittest.main()
