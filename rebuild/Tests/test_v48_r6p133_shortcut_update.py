"""Shortcut release, native same-host fence and metadata contracts."""
from pathlib import Path
import importlib.util
import unittest
import tempfile, zipfile, plistlib, json
ROOT=Path(__file__).resolve().parents[1]

class ShortcutUpdate(unittest.TestCase):
    def test_native_action_and_fixed_release_origin(self):
        s=(ROOT/'HostApp/ScarletSelfUpdateIntent.swift').read_text()
        for needle in ('struct ScarletSelfUpdateIntent: AppIntent','openAppWhenRun = true',
                       'api.github.com/repos/fx564286/sidestore-auto-refresh/releases',
                       'ScarletDeviceInstaller.install(', 'selfUpdateHostPath:',
                       'SHA256()', 'ownerVerified', 'installed_build_verified',
                       'currentBuild < candidate.build', 'Task.checkCancellation()'):
            self.assertIn(needle,s)
    def test_signed_target_fence_before_coredata_or_install(self):
        wire=(ROOT/'integration/wire_scarlet_auth.py').read_text()
        worker=(ROOT/'integration/ScarletDeviceInstallAgent.swift.txt').read_text()
        self.assertIn('selfUpdateHostPath',wire)
        self.assertIn('ScarletDeviceInstallAgent.validateSelfUpdateTarget(resignedAppBundle)',wire)
        self.assertIn('verifiedSameTeamManualHostURL',worker)
        self.assertIn('expected.extensionIDs == Set',worker)
        self.assertIn('expected.version == app.infoPlist["CFBundleVersion"] as? String',worker)
    def test_metadata_merge_preserves_existing_actions_and_rejects_collision(self):
        spec=importlib.util.spec_from_file_location('pack',ROOT/'integration/package_paired.py')
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        existing={'version':1,'actions':{'RefreshAllIntent':{'x':1}},'autoShortcuts':[{'x':1}]}
        host={'version':1,'actions':{'ScarletSelfUpdateIntent':{'fullyQualifiedTypeName':'LiveContainerSwiftUI.ScarletSelfUpdateIntent'}}}
        out=mod.merge_self_update_action(existing,host)
        self.assertEqual(out['actions']['RefreshAllIntent'],{'x':1})
        self.assertEqual(out['autoShortcuts'],existing['autoShortcuts'])
        self.assertIn('ScarletSelfUpdateIntent',out['actions'])
        self.assertNotIn('ScarletSelfUpdateIntent',existing['actions'])
        with self.assertRaises(ValueError):mod.merge_self_update_action(out,host)
        with self.assertRaises(ValueError):mod.merge_self_update_action(existing,{'version':1,'actions':{}})
    def test_archive_gate_requires_extracted_native_action_and_old_actions(self):
        spec=importlib.util.spec_from_file_location('gate',ROOT/'integration/verify_integrated_release.py')
        gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
        sha='a'*40
        host='Frameworks/LiveContainerSwiftUI.framework/'
        meta='Metadata.appintents/extract.actionsdata'
        action={'fullyQualifiedTypeName':'LiveContainerSwiftUI.ScarletSelfUpdateIntent'}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'combined.ipa'
            def fixture(missing=None):
                with zipfile.ZipFile(p,'w') as z:
                    z.writestr(gate.PREFIX+'Info.plist',plistlib.dumps({
                        'CFBundleIdentifier':'com.kdt.livecontainer.P8EZT3U5N4',
                        'CFBundleShortVersionString':'3.8.11','CFBundleVersion':'3.8.133',
                        'CFBundleExecutable':'LiveContainer'}))
                    for path,markers in gate.REQUIRED_MARKERS.items():
                        data=b'\x00'.join(markers)
                        if path==host+'LiveContainerSwiftUI':
                            data+=b'\x00scarlet-source-commit:'+sha.encode()
                            data+=b'\x00ScarletSelfUpdateIntent\x00shortcut_update_installed_build_verified'
                        if path=='Frameworks/SideStoreApp.framework/SideStore' and missing!='worker':
                            data+=b'\x00self_update_identity_unverified\x00Scarlet self-update signed identity or version mismatch'
                        z.writestr(gate.PREFIX+path,data)
                    old={k:{} for k in ('RefreshAllIntent','RefreshAllAppsWidgetIntent','InstallIPAIntent')}
                    if missing!='root':old['ScarletSelfUpdateIntent']=action
                    if missing=='legacy':old.pop('RefreshAllIntent')
                    z.writestr(gate.PREFIX+meta,json.dumps({'actions':old}))
                    z.writestr(gate.PREFIX+host+meta,json.dumps({'actions':{
                        'ScarletSelfUpdateIntent':action if missing!='native' else {}}}))
            fixture();receipt=gate.verify(p,'3.8.133',sha)
            self.assertEqual(receipt['size'],p.stat().st_size)
            self.assertEqual(receipt['bundleIdentifier'],'com.kdt.livecontainer.P8EZT3U5N4')
            for missing in ('root','legacy','native','worker'):
                fixture(missing)
                with self.assertRaises(ValueError):gate.verify(p,'3.8.133',sha)
    def test_release_manifest_gate(self):
        wf=(ROOT.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
        self.assertIn('scarlet-update.json',wf)
        self.assertIn('verify_integrated_release.py',wf)
        gate=(ROOT/'integration/verify_integrated_release.py').read_text()
        self.assertIn('ScarletSelfUpdateIntent',gate)
        self.assertIn('Metadata.appintents/extract.actionsdata',gate)
    def test_foreign_team_certificate_remains_stored_without_host_reinstall(self):
        panel=(ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text()
        body=panel.split('private func renewHostWithImportedSelectedCertificate(',1)[1].split('private func importExportedP12()',1)[0]
        self.assertLess(body.index('ScarletSigningReadiness.authorizedSideStoreGroupID()'),body.index('refreshing = true'))
        self.assertLess(body.index('"host_selected_team_mismatch"'),body.index('ScarletInstalledProfileReadback.beginRequest'))
        self.assertIn('await ScarletNativeSavedAccounts.importSelectedTeamCertificate(',panel)
        recorder=(ROOT/'HostApp/ScarletDiagnosticRecorder.swift').read_text()
        for category in ('selected_p12_host_resign_failed','selected_p12_host_resign_blocked','account_p12_guest_signer_blocked','v48_original_pan_observed'):
            self.assertIn('"'+category+'"',recorder.split('fixedLongCategories:',1)[1].split('private static func sanitized',1)[0])
if __name__=='__main__':unittest.main()
