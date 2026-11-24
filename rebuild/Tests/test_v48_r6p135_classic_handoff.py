"""P134 device: original launch requested repeatedly with live resident ownership."""
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[1]
H=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
S=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class ClassicHandoff(unittest.TestCase):
    def test_conflict_is_detected_before_history_or_upstream_run(self):
        body=H.split('private func runGuest(_ key: String)',1)[1].split('private func requestGuestUninstall',1)[0]
        self.assertLess(body.index('fullscreenStack.classicHandoffRequired'),body.index('ScarletGuestSessionLedger.noteLaunch('))
        self.assertIn('pendingClassicGuestKey = key',body)
        self.assertIn('!experimentalFullscreenResident',body)
        self.assertIn('MultitaskManager.isMultitasking()',body)
    def test_confirmation_is_only_owner_termination_entry(self):
        self.assertIn('종료 후 기본 모드 실행',H)
        self.assertIn('미저장 작업',H)
        self.assertEqual(H.count('await fullscreenStack.prepareClassicHandoff()'),1)
        self.assertIn('guard !experimentalFullscreenResident, launchingGuestKeys.isEmpty',H)
        self.assertIn('runGuest(key)',H.split('private func confirmClassicHandoff',1)[1].split('private func requestGuestUninstall',1)[0])
    def test_handoff_requires_native_registry_clear_and_no_pending_start(self):
        b=S.split('func prepareClassicHandoff() async -> Bool',1)[1].split('func livePID',1)[0]
        for x in ('!pendingInPlaceLaunch','pendingClassicFallback.isEmpty','slots.contains(where:', 'classicHandoffInProgress = true','await','!MultitaskManager.isMultitasking()','!hasResidentSession'):
            self.assertIn(x,b,x)
        self.assertIn('classicTerminationControllers.add(controller)',b)
        self.assertLess(b.index('classicTerminationControllers.add'),b.index('controller.terminate()'))
    def test_only_exact_owned_live_controllers_are_terminated(self):
        b=S.split('func classicHandoffControllers(',1)[1].split('func isRemoteReady',1)[0]
        for x in ('controller.pid == slot.pid','controller.dataUUID == slot.dataUUID','$0.isAppRunning','controllers.values'):
            self.assertIn(x,b,x)
        self.assertNotIn('kill(',b)
    def test_deliberate_exit_does_not_spawn_compatibility_fallback(self):
        self.assertIn('classicTerminationControllers.remove(vc)',S)
        self.assertIn('if fastExit && wasActive && !deliberateClassicExit',S)
        self.assertIn('guard !classicHandoffInProgress',S.split('private func switchOrLaunch',1)[1])
    def test_distinct_build_identity(self):
        self.assertIn('fix/scarlet-r6p135-classic-handoff-20261124',W)
        self.assertIn('3.8.135',W)
        self.assertIn('Scarlet-Crystal-V48-R6P135-CLASSIC-HANDOFF-UNSIGNED.ipa',W)
        self.assertIn('scarlet-v48-r6p135-classic-handoff-unsigned-20261124',W)

    def test_archive_rejects_missing_p135_compiled_receipts(self):
        import importlib.util, json, plistlib, tempfile, zipfile
        spec=importlib.util.spec_from_file_location('gate135',R/'integration/verify_integrated_release.py')
        gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
        sha='a'*40
        host='Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI'
        worker='Frameworks/SideStoreApp.framework/SideStore'
        actions={k:{} for k in ('RefreshAllIntent','RefreshAllAppsWidgetIntent','InstallIPAIntent')}
        actions['ScarletSelfUpdateIntent']={'fullyQualifiedTypeName':'LiveContainerSwiftUI.ScarletSelfUpdateIntent'}
        with tempfile.TemporaryDirectory() as tmp:
            ipa=Path(tmp)/'test.ipa'
            def fixture(missing=None):
                with zipfile.ZipFile(ipa,'w') as z:
                    z.writestr(gate.PREFIX+'Info.plist',plistlib.dumps({'CFBundleIdentifier':'com.kdt.livecontainer.P8EZT3U5N4','CFBundleShortVersionString':'3.8.11','CFBundleVersion':'3.8.135','CFBundleExecutable':'LiveContainer'}))
                    for path,markers in gate.REQUIRED_MARKERS.items():
                        data=list(markers)
                        if path==host:
                            data.extend([('scarlet-source-commit:'+sha).encode(),b'ScarletSelfUpdateIntent',b'shortcut_update_installed_build_verified',b'classic_handoff_drained',b'classic_handoff_blocked'])
                        if path==worker:
                            data.extend([b'self_update_identity_unverified',b'Scarlet self-update signed identity or version mismatch',b'self_update_archive_unverified',b'Scarlet self-update archive digest mismatch',b'Scarlet self-update source topology mismatch',b'Scarlet self-update provisioning Team mismatch'])
                        z.writestr(gate.PREFIX+path,b'\x00'.join(m for m in data if m!=missing))
                    for path in ('Metadata.appintents/extract.actionsdata','Frameworks/LiveContainerSwiftUI.framework/Metadata.appintents/extract.actionsdata'):
                        z.writestr(gate.PREFIX+path,json.dumps({'actions':actions}))
            fixture()
            self.assertEqual(gate.verify(ipa,'3.8.135',sha)['version'],'3.8.135')
            for marker in (b'classic_handoff_drained',b'classic_handoff_blocked'):
                fixture(marker)
                with self.assertRaisesRegex(ValueError,'R135'):
                    gate.verify(ipa,'3.8.135',sha)
