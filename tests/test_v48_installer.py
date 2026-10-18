import subprocess
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class InstallerTests(unittest.TestCase):
    def test_versioned_installer(self):
        text = (ROOT/'scripts/nrg_v48_widgetless_install_oneclick.sh').read_text()
        for marker in ('BRANCH=fix/nrg-v48-madeira-runtime-20261018','B=com.kdt.livecontainer.P8EZT3U5N4','missing/expired development profiles','increased_memory_granted=','ideviceinstaller -u "$U" upgrade "$S"'):
            self.assertIn(marker,text)
        self.assertNotIn('ideviceinstaller -u "$U" uninstall',text)
        self.assertEqual(subprocess.run(['bash','-n',str(ROOT/'scripts/nrg_v48_widgetless_install_oneclick.sh')]).returncode,0)
if __name__=='__main__': unittest.main()
