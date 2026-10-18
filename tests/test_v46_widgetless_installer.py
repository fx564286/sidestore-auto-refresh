"""Contract checks for the four-profile no-widget upgrade (never a fresh install)."""
import datetime
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/nrg_v46_widgetless_install_oneclick.sh'
TEAM = 'P8EZT3U5N4'
HOST = 'com.kdt.livecontainer.' + TEAM
SUFFIXES = ('LiveProcess','ShareExtension','LaunchAppExtension')

class WidgetlessInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.profiles = self.root / 'profiles'
        self.profiles.mkdir()
        fake = self.root / 'bin'
        fake.mkdir()
        openssl = fake / 'openssl'
        openssl.write_text('''#!/usr/bin/env python3
import pathlib,sys
sys.stdout.buffer.write(pathlib.Path(sys.argv[sys.argv.index('-in')+1]).read_bytes())
''')
        openssl.chmod(0o755)
        self.env = dict(os.environ, I=str(self.root/'sample.ipa'),C=str(self.profiles),
                        B=HOST, TEAM=TEAM, U='00008160-000569490C600036',P=str(self.root/'profiles.txt'),
                        PATH=str(fake)+':'+os.environ['PATH'])
        self.python_block = SCRIPT.read_text().split("python3 - <<'PY'\n")[1].split('\nPY\n')[0]

    def create_ipa(self, widget=False):
        with zipfile.ZipFile(self.env['I'],'w') as archive:
            archive.writestr('Payload/LiveContainer.app/Info.plist',plistlib.dumps({'CFBundleIdentifier':'com.kdt.livecontainer'}))
            for suffix in SUFFIXES + (('LiveWidget',) if widget else ()):
                name = 'LiveWidgetExtension' if suffix == 'LiveWidget' else suffix
                archive.writestr(f'Payload/LiveContainer.app/PlugIns/{name}.appex/Info.plist',
                                 plistlib.dumps({'CFBundleIdentifier':'com.kdt.livecontainer.'+suffix}))

    def create_profiles(self,missing=None, debug=True):
        for ix, identity in enumerate((HOST,)+tuple(HOST+'.'+s for s in SUFFIXES)):
            if identity == missing:continue
            self.profiles.joinpath(f'profile-{ix}.mobileprovision').write_bytes(plistlib.dumps({
                'Entitlements':{'application-identifier':TEAM+'.'+identity,'get-task-allow':debug},
                'TeamIdentifier':[TEAM],'ProvisionedDevices':[self.env['U']],
                'ExpirationDate':datetime.datetime(2030,1,1),
            }))

    def run_preflight(self):
        return subprocess.run(['python3','-c',self.python_block],env=self.env,text=True,capture_output=True)

    def test_accepts_exact_three_extensions_and_four_debuggable_profiles(self):
        self.create_ipa();self.create_profiles()
        result=self.run_preflight()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(Path(self.env['P']).read_text().splitlines()),4)
        self.assertIn('no widget',result.stdout)

    def test_rejects_existing_widget(self):
        self.create_ipa(widget=True);self.create_profiles()
        result=self.run_preflight()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('exactly 3 expected extensions',result.stderr)

    def test_rejects_missing_extension_profile(self):
        self.create_ipa();self.create_profiles(missing=HOST+'.ShareExtension')
        result=self.run_preflight()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('missing/expired development profiles',result.stderr)

    def test_rejects_non_debuggable_profile(self):
        self.create_ipa();self.create_profiles(debug=False)
        result=self.run_preflight()
        self.assertNotEqual(result.returncode,0)
        self.assertIn('get-task-allow',result.stderr)

    def test_never_uninstalls_or_changes_bundle_id(self):
        s=SCRIPT.read_text()
        self.assertIn('ideviceinstaller -u "$U" upgrade "$S"',s)
        self.assertNotIn('ideviceinstaller -u "$U" uninstall',s)
        self.assertIn('B=com.kdt.livecontainer.P8EZT3U5N4',s)
        self.assertNotIn('LiveWidget.mobileprovision',s)

if __name__=='__main__':unittest.main()
