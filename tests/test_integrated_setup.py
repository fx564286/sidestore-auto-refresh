import importlib.util
import os
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/'installer'
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
impl=load('scarlet_oneclick')
patcher=load('install_integration')


def result(stdout='',returncode=0,stderr=''):
    return subprocess.CompletedProcess([],returncode,stdout,stderr)


def record(path):
    Path(path).write_bytes(plistlib.dumps({'identifier':'test-host', 'public_key':b'P'*32, 'private_key':b'S'*32}))

class Setup(unittest.TestCase):
    def test_existing_verified_record_is_reused(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td); record(cache/'Scarlet-RemotePairing.plist')
            calls=[]
            def runner(args,timeout):
                calls.append(args)
                if 'verify' in args:return result('the device recognizes this pairing record')
                raise AssertionError('No new pair should be generated')
            setup=impl.SetupBackend(cache=cache,runner=runner,fetcher=lambda p: Path('/fake/idevice-tools'))
            info=[]
            self.assertEqual(setup.prepare(info.append),cache/'Scarlet-RemotePairing.plist')
            self.assertTrue(any('재사용' in s for s in info))
            self.assertFalse(any('pair' in c for c in calls))

    def test_new_record_only_committed_after_actual_pair_verify(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td)
            def runner(args,timeout):
                if args[-4:-2] == ['remotepairing_lockdown','pair']:
                    record(args[-1]);return result('paired, saved')
                if 'verify' in args:return result('the device recognizes this pairing record')
                raise AssertionError(args)
            setup=impl.SetupBackend(cache=cache,runner=runner,fetcher=lambda p: Path('/fake/tool'))
            self.assertEqual(setup.prepare(lambda _:None),cache/'Scarlet-RemotePairing.plist')
            self.assertTrue(impl.parse_rp(setup.pair_file))

    def test_failed_pair_verification_keeps_original_and_no_install(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td);p=cache/'Scarlet-RemotePairing.plist';record(p)
            old=p.read_bytes()
            def runner(args,timeout):
                if 'pair' in args:record(args[-1]);return result('paired')
                if 'verify' in args:return result('pair-verify failed',0)
                raise AssertionError(args)
            setup=impl.SetupBackend(cache=cache,runner=runner,fetcher=lambda p:Path('/fake/tool'))
            with self.assertRaises(impl.SetupError):setup.prepare(lambda _:None)
            self.assertEqual(p.read_bytes(),old)

    def test_idevice_exit_zero_but_pair_rejected_is_not_success(self):
        self.assertFalse(impl.recognized(result('pair-verify failed',0)))
        self.assertFalse(impl.recognized(result('the device recognizes this pairing record',1)))
        self.assertTrue(impl.recognized(result('the device recognizes this pairing record',0)))

    def test_pair_file_must_contain_real_fixed_length_keys(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'bad.plist'
            p.write_bytes(plistlib.dumps({'identifier':'x','public_key':b'bad','private_key':b'S'*32}))
            with self.assertRaises(impl.SetupError):impl.parse_rp(p)

    def test_stage_only_to_inbox_not_live_record(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td);record(cache/'Scarlet-RemotePairing.plist')
            calls=[]
            def runner(args,timeout):
                calls.append(args)
                return result('ok')
            setup=impl.SetupBackend(cache=cache,runner=runner,fetcher=lambda p:Path('/fake/tool'))
            setup.binary=Path('/fake/tool')
            self.assertTrue(setup.stage_pairing(lambda _:None))
            upload=[c for c in calls if 'upload' in c]
            self.assertEqual(len(upload),1)
            self.assertEqual(upload[0][-1],'/Documents/Inbox/Scarlet-RemotePairing.plist')

    def test_host_patch_preserves_old_window(self):
        src=('from PySide6.QtWidgets import QWidget\n'
             'class Window(QWidget):\n'
             '    def make_ui(self):\n'
             '        self.actions_row = object()\n'
             '        self.both_btn = object()\n'
             '        return 1\n'
             '    def sign_original(self):\n'
             '        return "preserved"\n'
             '\nif __name__=="__main__":\n    Window()\n')
        p=patcher.patch(src)
        self.assertEqual(patcher.patch(p),p)
        self.assertIn('def sign_original(self)',p)
        self.assertIn('    return "preserved"',p)
        self.assertEqual(p.count(patcher.MARK),1)
        self.assertLess(p.index('scarlet_oneclick import enable'),p.index('if __name__'))

    def test_unknown_gui_fails_closed(self):
        for source in ['class Window:\n    pass\n', 'def make_ui():\n    pass\n']:
            with self.assertRaises(RuntimeError):patcher.patch(source)

    def test_installer_patches_existing_gui_only_with_backup(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/'launch.sh').write_text('echo running\n')
            original=('class Window:\n    def make_ui(self):\n'
                '        self.actions_row = 1\n'
                '        self.both_btn = 2\n'
                '        return None\n')
            (root/'scarlet_gui.py').write_text(original)
            folder,backup=patcher.install(root)
            self.assertEqual(Path(backup,'scarlet_gui.py').read_text(),original)
            self.assertIn(patcher.MARK,(root/'scarlet_gui.py').read_text())
            self.assertTrue((root/'scarlet_oneclick.py').is_file())
            self.assertEqual((root/'launch.sh').read_text(),'echo running\n')

if __name__=='__main__':unittest.main()
