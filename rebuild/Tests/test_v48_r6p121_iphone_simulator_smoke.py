"""Contract for a genuine macOS iPhone Simulator build/install/launch probe."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT/'rebuild/diagnostics/scarlet_ios_simulator_smoke.py'
WORKFLOW = (ROOT/'.github/workflows/scarlet-paired-engines-build.yml').read_text()


class SimulatorSmoke(unittest.TestCase):
    def test_genuine_iphone_runtime_selection_only(self):
        spec=importlib.util.spec_from_file_location('iphone_smoke',SCRIPT)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        info={'devices':{
            'com.apple.CoreSimulator.SimRuntime.iOS-27-2':[
                {'name':'iPhone 17 Pro','udid':'iphone27','state':'Shutdown','isAvailable':True},
                {'name':'iPad Pro','udid':'ipad27','state':'Shutdown','isAvailable':True}],
            'com.apple.CoreSimulator.SimRuntime.iOS-26-0':[
                {'name':'iPhone 16','udid':'iphone26','state':'Booted','isAvailable':True}],
            'com.apple.CoreSimulator.SimRuntime.watchOS-12-0':[
                {'name':'Apple Watch','udid':'watch','state':'Shutdown','isAvailable':True}]}}
        chosen=module.select_iphone(info)
        self.assertEqual(chosen['udid'],'iphone26')
        self.assertIsNone(module.select_iphone({'devices':{'iOS-27':[{'name':'iPad','udid':'ipad','isAvailable':True}]}}))

    def test_workflow_runs_real_iphonesimulator_build_not_device_ipa_install(self):
        self.assertIn('rebuild/diagnostics/scarlet_ios_simulator_smoke.py',WORKFLOW)
        self.assertIn('engine/LiveContainer',WORKFLOW)
        self.assertIn('if: always()',WORKFLOW)
        src=SCRIPT.read_text()
        for required in ('xcrun', 'simctl', 'bootstatus', 'iphonesimulator',
                         'xcodebuild', 'LiveContainer.xcodeproj',
                         'simctl', 'install', 'launch', 'screenshot', 'smoke.json'):
            self.assertIn(required,src)
        self.assertIn('simulator_build_failed',src)
        self.assertIn('simulator_launch_failed',src)
        self.assertIn('simulator_launch_screenshot_captured',src)
        self.assertNotIn('Apple ID', src)  # No mock account sign-in or copied credentials.

    def test_macos_bash32_test_harness_has_nonempty_array(self):
        harness=(ROOT/'rebuild/Tests/test_v48_r6p121_release_identity_chain.py').read_text()
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(__unset__)',harness)
        self.assertNotIn("'SCARLET_HOST_VERSION_ARGS=()\\n'",harness)


if __name__ == '__main__':
    unittest.main()


class SimulatorCompileFirst(unittest.TestCase):
    @staticmethod
    def module():
        spec=importlib.util.spec_from_file_location('iphone_smoke_compilefirst',SCRIPT)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_successful_simulator_build_remains_visible_even_when_boot_times_out(self):
        import json
        import plistlib
        import tempfile
        from unittest.mock import patch
        m=self.module()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            app=root/'LiveContainer.app'
            app.mkdir()
            (app/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'test.scarlet.smoke'}))
            observations=[]

            def build(*args,**kwargs):
                observations.append('xcodebuild')
                return app

            def fake_run(args,*,stage,timeout=100,cwd=None):
                observations.append(' '.join(args))
                if args[:4]==['xcrun','simctl','list','-j']:
                    return json.dumps({'devices':{
                        'com.apple.CoreSimulator.SimRuntime.iOS-27-2':[
                            {'name':'iPhone 18 Pro','udid':'sim-test-id','state':'Shutdown','isAvailable':True}]}})
                if args[:3]==['xcrun','simctl','bootstatus']:
                    raise m.SmokeBlocked('simulator_boot_failed','command_unavailable_or_timeout:TimeoutExpired')
                return ''

            with patch.object(m,'simulator_build',side_effect=build), \
                 patch.object(m,'run',side_effect=fake_run), \
                 patch('sys.argv',['smoke','--engine',str(root),'--report-dir',str(root/'report')]):
                self.assertEqual(m.main(),2)
            report=json.loads((root/'report/smoke.json').read_text())
            self.assertEqual(observations[0],'xcodebuild')
            self.assertEqual(report['simulator_build'],'passed')
            self.assertEqual(report['app_bundle_id'],'test.scarlet.smoke')
            self.assertEqual(report['stage'],'simulator_boot_failed')
            self.assertEqual(report['result'],'blocked')
            self.assertNotIn('screenshot_bytes',report)

    def test_failed_simulator_compilation_stops_before_simctl_and_records_stage(self):
        import json
        import tempfile
        from unittest.mock import patch
        m=self.module()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            with patch.object(m,'simulator_build',side_effect=m.SmokeBlocked(
                'simulator_build_failed','simulator_target_unsupported')), \
                 patch.object(m,'run',side_effect=AssertionError('boot_must_not_run')), \
                 patch('sys.argv',['smoke','--engine',str(root),'--report-dir',str(root/'report')]):
                self.assertEqual(m.main(),2)
            report=json.loads((root/'report/smoke.json').read_text())
            self.assertEqual(report['simulator_build'],'failed')
            self.assertEqual(report['stage'],'simulator_build_failed')
            self.assertEqual(report['result'],'blocked')

    def test_prebooted_iphone_is_preferred_over_newer_shutdown_runtime(self):
        m=self.module()
        inventory={'devices':{
            'com.apple.CoreSimulator.SimRuntime.iOS-27-2':[
                {'name':'iPhone 18 Pro','udid':'newer-off','state':'Shutdown','isAvailable':True}],
            'com.apple.CoreSimulator.SimRuntime.iOS-26-0':[
                {'name':'iPhone 17','udid':'older-on','state':'Booted','isAvailable':True}]}}
        self.assertEqual(m.select_iphone(inventory)['udid'],'older-on')
