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
        self.assertEqual(chosen['udid'],'iphone27')
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
