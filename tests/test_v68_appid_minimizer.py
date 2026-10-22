"""No fixed App ID number: preserve features, prove each installed extension has a reason."""
import json
import plistlib
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from v68_appid_minimizer import select, load_policy, shell_environment, verify_archive


class AdaptiveMinimalAppIDTests(unittest.TestCase):
    def test_feature_preserving_minimum_keeps_actual_share_sheet(self):
        plan = load_policy(ROOT / 'config/v68_required_features.json')
        self.assertEqual(4, plan['minimum_planned_app_ids'])
        self.assertEqual({'host','LiveProcess','LiveWidget','ShareExtension'}, set(plan['installable_roles']))
        self.assertEqual([], plan['disabled_or_not_requested_features'])
        self.assertTrue(plan['build_supported_by_current_v67_source'])
        self.assertIn('NRG_V67_3IDS=0', shell_environment(plan))

    def test_shortcuts_fallback_3_ids_explicitly_loses_native_share_destination(self):
        requirements = load_policy(ROOT / 'config/v68_required_features.json')['features']
        requirements['native_share_sheet_receiver'] = False
        plan = select(requirements)
        self.assertEqual(3, plan['minimum_planned_app_ids'])
        self.assertTrue(plan['build_supported_by_current_v67_source'])
        self.assertIn('NRG_V67_3IDS=1', shell_environment(plan))
        self.assertTrue(any('not identical' in x for x in plan['limitations']))

    def test_two_and_one_ids_are_not_falsely_reported_as_buildable(self):
        for widgets, guests, expected in ((True,False,2),(False,False,1)):
            plan = select({'native_dynamic_island': widgets, 'independent_guest_process': guests})
            self.assertEqual(expected, plan['minimum_planned_app_ids'])
            self.assertFalse(plan['build_supported_by_current_v67_source'])
            with self.assertRaisesRegex(ValueError,'unimplemented'):
                shell_environment(plan)

    def test_unmapped_native_api_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'Unmapped Apple API'):
            select({'native_dynamic_island': True, 'unreviewed_new_extension': True})
        with self.assertRaises(ValueError):
            select({'native_dynamic_island': 'yes'})

    @staticmethod
    def sample_ipa(path, extensions):
        info = {'CFBundleIdentifier': 'com.kdt.livecontainer', 'NSSupportsLiveActivities': True,
                'CFBundleDocumentTypes': [{'LSItemContentTypes':['public.item']}]}
        with zipfile.ZipFile(path,'w') as package:
            package.writestr('Payload/LiveContainer.app/Info.plist', plistlib.dumps(info))
            for ext in extensions:
                package.writestr(f'Payload/LiveContainer.app/PlugIns/{ext}.appex/Info.plist',
                    plistlib.dumps({'CFBundleIdentifier': 'com.kdt.livecontainer.'+ext}))

    def test_ipa_enforces_exact_roles_4_and_3(self):
        full = load_policy(ROOT / 'config/v68_required_features.json')
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'test.ipa'
            self.sample_ipa(archive, ['LiveProcess','LiveWidget','ShareExtension'])
            self.assertEqual(4, verify_archive(archive, full)['verified_app_ids'])
            fallback_features = full['features'].copy()
            fallback_features['native_share_sheet_receiver'] = False
            compact = select(fallback_features)
            with self.assertRaisesRegex(ValueError,'bundle mismatch'):
                verify_archive(archive, compact)
            self.sample_ipa(archive, ['LiveProcess','LiveWidget'])
            self.assertEqual(3, verify_archive(archive, compact)['verified_app_ids'])

    def test_no_fixed_numeric_cap_in_current_feature_policy(self):
        registry = json.loads((ROOT / 'config/v67_api_modules.json').read_text())
        self.assertNotIn('app_id_cap', registry)
        workflow = (ROOT / '.github/workflows/livecontainer-build.yml').read_text()
        self.assertIn('v68_appid_minimizer.py', workflow)
        self.assertIn("expected=set(plan['expected_unsigned_bundle_ids'][1:])",workflow)


if __name__ == '__main__':
    unittest.main()
