"""R6P132 integrated artifact and refresh preflight regression contracts."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
WORKER=(ROOT/'integration/ScarletGuestRefreshAgent.swift.txt').read_text()
XPC=(ROOT/'HostApp/ScarletAuthXPCSupport.swift').read_text()
AUTO=(ROOT/'HostApp/ScarletAutomaticRenewal.swift').read_text()
WF=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
SHA='a'*40
PREFIX='Payload/LiveContainer.app/'

class IntegratedRelease(unittest.TestCase):
    def test_preflight_uses_team_gate_and_releases_before_reply(self):
        body=WORKER.split('static func inspectHostBundle(',1)[1].split('// Refresh exactly',1)[0]
        self.assertLess(body.index('await ScarletTeamOperationGate.shared.claim()'),body.index('DatabaseManager.shared.start()'))
        self.assertIn('reply(0, false, false, "team_operation_in_progress")',body)
        self.assertLess(body.index('await ScarletTeamOperationGate.shared.release()'),body.index('reply(count, managesHost, signingReady, reason)'))
        self.assertIn('"team_operation_in_progress"', XPC.split('public enum ScarletNativeRefreshInspector',1)[1].split('// Original SideStore AppManager',1)[0])
        self.assertIn('nativeState.reason == "team_operation_in_progress"',AUTO)
    def test_settings_deferred_due_work_resumes_on_exit(self):
        self.assertIn('private var pendingSettingsCatchUp = false',AUTO)
        self.assertIn('pendingVerifiedAccountSwitch || pendingSettingsCatchUp',AUTO)
        self.assertEqual(AUTO.count('pendingSettingsCatchUp = true'),2)
    def test_archive_gate_rejects_mixed_binary_or_wrong_version(self):
        spec=importlib.util.spec_from_file_location('gate',ROOT/'integration/verify_integrated_release.py')
        gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'combined.ipa'
            def fixture(version='3.8.132',missing=None,sha=SHA):
                with zipfile.ZipFile(p,'w') as z:
                    z.writestr(PREFIX+'Info.plist',plistlib.dumps({'CFBundleIdentifier':'com.kdt.livecontainer.P8EZT3U5N4','CFBundleShortVersionString':'3.8.11','CFBundleVersion':version,'CFBundleExecutable':'LiveContainer'}))
                    for path,markers in gate.REQUIRED_MARKERS.items():
                        data=b'\x00'.join(marker for marker in markers if marker!=missing)
                        if path=='Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI':
                            data+=b'\x00'+('scarlet-source-commit:'+sha).encode()
                        z.writestr(PREFIX+path,data)
            fixture();self.assertEqual(gate.verify(p,'3.8.132',SHA)['sourceCommit'],SHA)
            fixture(version='3.8.131')
            with self.assertRaises(ValueError):gate.verify(p,'3.8.132',SHA)
            for marker in [b'classic_bootstrap_armed',b'scarlet.certificate.team_operation_in_progress',b'automatic_deferred_interactive_settings']:
                fixture(missing=marker)
                with self.assertRaises(ValueError):gate.verify(p,'3.8.132',SHA)
            fixture(sha='b'*40)
            with self.assertRaises(ValueError):gate.verify(p,'3.8.132',SHA)
    def test_ci_enforces_gate_before_upload_and_checks_same_bytes_before_publish(self):
        self.assertIn('verify_integrated_release.py',WF)
        self.assertIn('integrated-release-verification.json',WF)
        self.assertIn('receipt["sourceCommit"] == os.environ["GITHUB_SHA"]',WF)
        self.assertIn('receipt["sha256"] == hashlib.file_digest',WF)

if __name__=='__main__': unittest.main()
