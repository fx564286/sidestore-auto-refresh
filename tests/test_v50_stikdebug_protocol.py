"""V50 source-level tests against pinned upstream LiveContainer + V49 patch."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def import_script(module_name, filename):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / 'scripts' / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v49 = import_script('v49_jit', 'patch_v49_auto_jit.py')
v50 = import_script('v50_jit', 'patch_v50_stikdebug_protocol.py')


class V50ProtocolTests(unittest.TestCase):
    def source(self, relative):
        override = os.environ.get('LIVE_CONTAINER_TEST_SOURCE')
        candidates = [Path(override) if override else None, ROOT / 'work' / 'LiveContainer']
        for parent in candidates:
            if parent is not None and (parent / relative).exists():
                return (parent / relative).read_text()
        self.skipTest('Pinned LiveContainer sources are not present locally')

    def test_multitask_pid_and_base64(self):
        v49_patched = v49.patch(self.source(v50.VIEW))
        result = v50.patch_view(v49_patched)
        self.assertEqual(v50.patch_view(result), result)
        self.assertIn('components.scheme = jitEnabler == .StikJITLC ? "stikjit" : "stikdebug"', result)
        self.assertIn('URLQueryItem(name: "pid", value: String(pid))', result)
        self.assertIn('URLQueryItem(name: "script-data", value: Data(script.utf8).base64EncodedString())', result)
        self.assertIn('NRG_V50_STIKDEBUG_PROTOCOL', result)
        self.assertIn('runtime_jit_unverified=1', result)
        self.assertNotIn('URLQueryItem(name: "script-data", value: script)', result)

    def test_classic_pid_and_base64(self):
        result = v50.patch_utils(self.source(v50.UTILS))
        self.assertEqual(v50.patch_utils(result), result)
        self.assertIn('URLQueryItem(name: "pid", value: String(getpid()))', result)
        self.assertIn('URLQueryItem(name: "script-data", value: Data(script.utf8).base64EncodedString())', result)
        self.assertIn('request.scheme = jitEnabler == .StikJITLC ? "stikjit" : "stikdebug"', result)
        self.assertNotIn('launchURLStr += "&script-data=\\(script)"', result)

    def test_fail_closed_without_v49(self):
        with self.assertRaises(RuntimeError):
            v50.patch_view('components.scheme = "stikjit"')
        with self.assertRaises(RuntimeError):
            v50.patch_utils('unrecognized source')

    def test_prevalidate_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            view = root / v50.VIEW
            utils = root / v50.UTILS
            view.parent.mkdir(parents=True)
            utils.parent.mkdir(parents=True)
            view.write_text('not v49')
            utils.write_text('not upstream')
            with self.assertRaises(RuntimeError):
                v50.main(root)
            self.assertEqual(view.read_text(), 'not v49')
            self.assertEqual(utils.read_text(), 'not upstream')

    def test_no_signing_device_or_data_changes(self):
        scripts = (ROOT / 'scripts' / 'patch_v50_stikdebug_protocol.py').read_text()
        for token in ('ideviceinstaller', 'uninstall ', 'mobileprovision', 'SecItemDelete(', 'Bundle.main.bundleIdentifier ='):
            self.assertNotIn(token, scripts)


if __name__ == '__main__':
    unittest.main()
