"""Contract checks for bounded App IDs with extensible host APIs."""
import importlib.util
import json
import os
from pathlib import Path
import plistlib
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from package_livecontainer_combined import adapt
from patch_v67_three_ids import assert_invariants, preflight
from v67_upstream_watch import pinned_sha, markdown


class V67ThreeAppIDsTests(unittest.TestCase):
    def test_document_import_open_in_requires_host_capability(self):
        target = os.getenv('LIVE_CONTAINER_TEST_SOURCE')
        if not target:
            self.skipTest('Needs upstream LiveContainer source')
        preflight(Path(target) / 'LiveContainer')
        with tempfile.TemporaryDirectory() as d:
            info = {'CFBundleDocumentTypes': [{'LSItemContentTypes': ['public.item']}],
                    'LSSupportsOpeningDocumentsInPlace': False}
            (Path(d)/'Info.plist').write_bytes(plistlib.dumps(info))
            with self.assertRaisesRegex(ValueError, 'documents-in-place'):
                preflight(Path(d))

    def test_retired_native_widget_v67_path_is_rejected_but_host_shortcuts_still_work(self):
        target = os.getenv('LIVE_CONTAINER_TEST_SOURCE')
        if not target:
            self.skipTest('Needs upstream source')
        original = (Path(target) / '.github' / 'build_github.sh').read_text()
        with patch.dict(os.environ, {'NRG_V66_4IDS': '1','NRG_V67_3IDS': '1','NRG_V58_NATIVE_ISLAND': '1'}, clear=True):
            with self.assertRaisesRegex(ValueError, "obsolete native-Island"):
                adapt(original)
        with patch.dict(os.environ, {'NRG_V66_4IDS': '1','NRG_V58_NATIVE_ISLAND': '0'}, clear=True):
            output = adapt(original)
        self.assertIn('rm -rf ./Payload/LiveContainer.app/PlugIns/LaunchAppExtension.appex',output)
        self.assertNotIn('rm -rf ./Payload/LiveContainer.app/PlugIns/ShareExtension.appex',output)
        self.assertNotIn('rm -rf ./Payload/LiveContainer.app/PlugIns/LiveProcess.appex',output)

    def test_v67_rejects_missing_native_island_or_app_intent(self):
        for setting in [{'NRG_V67_3IDS': '1','NRG_V66_4IDS': '1'},
                        {'NRG_V67_3IDS': '1','NRG_V58_NATIVE_ISLAND': '1'}]:
            with patch.dict(os.environ, setting, clear=True):
                with self.assertRaises(ValueError):
                    assert_invariants()

    def test_exact_id_cap_ci(self):
        workflow = (ROOT / '.github/workflows/livecontainer-build.yml').read_text()
        if 'v68_appid_minimizer.py' in workflow:
            self.assertIn('builder/config/v68_required_features.json', workflow)
            self.assertIn("expected=set(plan['expected_unsigned_bundle_ids'][1:])", workflow)
        else:
            self.assertIn('NRG_V67_3IDS: "1"', workflow)
            self.assertIn("('LiveProcess','LiveWidget')", workflow)
        self.assertIn("assert found==expected,(found,expected)", workflow)
        packager = (ROOT/'scripts/package_livecontainer_combined.py').read_text()
        self.assertIn("assert result['registration_targets_before_reuse'] == 2",packager)
        self.assertIn("'public.item'", packager)

    def test_upstream_watch_never_floats_build_refs(self):
        workflow = (ROOT / '.github/workflows/livecontainer-build.yml').read_text()
        live = pinned_sha(workflow,'LIVE_CONTAINER_REF')
        side = pinned_sha(workflow,'EMBEDDED_SIDESTORE_REF')
        self.assertEqual(len(live),40)
        self.assertEqual(len(side),40)
        data={'upstreams':{'a':{'repository':'LiveContainer/LiveContainer', 'branch':'main',
                               'upstream':{'sha': live,'url':'https://github.com/LiveContainer/LiveContainer'},
                               'pinned': live, 'update_available': False}},
              'sdk_observed':{'xcode':'Xcode test','iphoneos_sdk':'test'}}
        rendered = markdown(data)
        # V68+ uses a feature-derived App ID minimum, not a fixed count.
        # Keep the security and update-integrity contract: immutable SHA
        # pins, required native extensions, device testing and no auto-release.
        self.assertIn('minimize App IDs by verified capabilities', rendered)
        self.assertIn('preserve required native extensions', rendered)
        self.assertIn('run device regression tests', rendered)
        self.assertIn('Do not publish or install a new IPA automatically.', rendered)
        self.assertIn(live[:12], rendered)
        self.assertIn('Current', rendered)
        self.assertNotIn('three-App-ID cap', rendered)

    def test_upstream_candidate_requires_review_without_autorelease(self):
        workflow = (ROOT / '.github/workflows/livecontainer-build.yml').read_text()
        live = pinned_sha(workflow, 'LIVE_CONTAINER_REF')
        candidate = 'f' * 40 if live != 'f' * 40 else 'e' * 40
        data = {'upstreams': {'a': {
            'repository': 'LiveContainer/LiveContainer',
            'branch': 'main',
            'upstream': {'sha': candidate,
                         'url': 'https://github.com/LiveContainer/LiveContainer'},
            'pinned': live,
            'update_available': True}},
            'sdk_observed': {'xcode': 'Xcode test', 'iphoneos_sdk': 'test'}}
        rendered = markdown(data)
        self.assertIn('Review + compatibility tests', rendered)
        self.assertIn(live[:12], rendered)
        self.assertIn(candidate[:12], rendered)
        self.assertIn('Do not publish or install a new IPA automatically.', rendered)


if __name__ == '__main__':
    unittest.main()
