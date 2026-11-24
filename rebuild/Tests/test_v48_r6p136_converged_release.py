"""Converged P135 runtime branches must be present in the same P136 IPA."""
import importlib.util
import json
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile

R = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gate136', R/'integration/verify_integrated_release.py')
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
HOST = 'Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI'
WORKER = 'Frameworks/SideStoreApp.framework/SideStore'
HOST_NEW = (b'selected_team_partial_refresh_results', b'selected_team_refresh_result_mismatch')
WORKER_NEW = (b'SideSign.DeveloperPortalError', b'selected_team_partial_refresh_results', b'selected_team_refresh_result_mismatch')
SHA = 'b'*40
BRANCH = 'fix/scarlet-r6p136-converged-20261124'

class ConvergedRelease(unittest.TestCase):
    def test_branch_has_unique_build_and_push_trigger(self):
        w = (R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
        self.assertIn(BRANCH, next(l for l in w.splitlines() if l.startswith('    branches:')))
        self.assertIn(f'elif [ "$GITHUB_REF" = "refs/heads/{BRANCH}" ]; then\n            SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.136)', w)

    def test_archive_requires_both_native_repair_paths(self):
        actions = {k: {} for k in ('RefreshAllIntent','RefreshAllAppsWidgetIntent','InstallIPAIntent')}
        actions['ScarletSelfUpdateIntent'] = {'fullyQualifiedTypeName':'LiveContainerSwiftUI.ScarletSelfUpdateIntent'}
        with tempfile.TemporaryDirectory() as tmp:
            ipa = Path(tmp)/'test.ipa'
            def fixture(missing=None):
                with zipfile.ZipFile(ipa,'w') as z:
                    z.writestr(GATE.PREFIX+'Info.plist', plistlib.dumps({'CFBundleIdentifier':'com.kdt.livecontainer.P8EZT3U5N4','CFBundleShortVersionString':'3.8.11','CFBundleVersion':'3.8.136','CFBundleExecutable':'LiveContainer'}))
                    for path, markers in GATE.REQUIRED_MARKERS.items():
                        data=list(markers)
                        if path==HOST:
                            data.extend([('scarlet-source-commit:'+SHA).encode(), b'ScarletSelfUpdateIntent', b'shortcut_update_installed_build_verified', b'classic_handoff_drained', b'classic_handoff_blocked', *HOST_NEW])
                        if path==WORKER:
                            data.extend([b'self_update_identity_unverified', b'Scarlet self-update signed identity or version mismatch', b'self_update_archive_unverified', b'Scarlet self-update archive digest mismatch', b'Scarlet self-update source topology mismatch', b'Scarlet self-update provisioning Team mismatch', *WORKER_NEW])
                        z.writestr(GATE.PREFIX+path,b'\0'.join(m for m in data if (path,m)!=missing))
                    for path in ('Metadata.appintents/extract.actionsdata','Frameworks/LiveContainerSwiftUI.framework/Metadata.appintents/extract.actionsdata'):
                        z.writestr(GATE.PREFIX+path,json.dumps({'actions':actions}))
            fixture()
            self.assertEqual(GATE.verify(ipa,'3.8.136',SHA)['version'],'3.8.136')
            for path, markers in ((HOST,HOST_NEW),(WORKER,WORKER_NEW)):
                for marker in markers:
                    with self.subTest(path=path,marker=marker):
                        fixture((path,marker))
                        with self.assertRaisesRegex(ValueError,'R136'):
                            GATE.verify(ipa,'3.8.136',SHA)

if __name__ == '__main__':
    unittest.main()
