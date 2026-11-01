"""On-device recovery must reuse upstream WirelessPairService, not PC helper."""
import importlib.util, pathlib, unittest, os
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('restore',ROOT/'scripts/patch_v167_restore_ondevice_pairing.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class V167OriginalPath(unittest.TestCase):
    def test_wire_contract_is_idempotent(self):
        before=(ROOT/'scripts/templates/v3_wire_contract.swift').read_text()
        after=m.patch_wire(before)
        self.assertEqual(m.patch_wire(after),after)
        self.assertIn('"wirelessPairStart"',after)
        self.assertIn('"wirelessPairStatus"',after)
        self.assertIn('"wirelessPairStop"',after)
        self.assertIn('"wirelessPairStatus",',after)
    def test_service_uses_existing_upstream_api(self):
        s=m.patch_service((ROOT/'scripts/templates/v3_sidestore_service.swift').read_text())
        self.assertIn('wirelessPairing.start(outPath: out.path)',s)
        self.assertIn('wirelessPairing.stop()',s)
        self.assertIn('PairingFileManager.shared.savePairingFile(contents: contents)',s)
        self.assertIn('PairingFileParser.parse(content: contents)',s)
        self.assertIn('[SCARLET_V167_ONDEVICE_HOST] phase=start pin=redacted',s)
        self.assertNotIn('idevice-tools',s)
        self.assertEqual(m.patch_service(s),s)
    def test_host_uses_native_service_not_pc(self):
        base=(ROOT/'scripts/templates/v3_unified_shell.swift').read_text()
        def read_patch(name):
            spec=importlib.util.spec_from_file_location(name,ROOT/('scripts/'+name+'.py'))
            x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x);return x
        base=read_patch('patch_v165_first_install_flow').patch(base)
        base=read_patch('patch_v166_integrated_rp').patch(base)
        s=m.patch_host(base)
        self.assertIn('"wirelessPairStart"',s)
        self.assertIn('"wirelessPairStatus"',s)
        self.assertIn('"wirelessPairStop"',s)
        self.assertIn('scarletV167OnDevicePair',s)
        self.assertIn('[SCARLET_V167_ONDEVICE_UI] action=start',s)
        self.assertIn('@Environment(\\.scenePhase)',s)
        self.assertNotIn('@Environment(\\\\.scenePhase)',s)
        self.assertEqual(m.patch_host(s),s)
    def test_save_is_atomic_without_early_delete(self):
        test='''        if fm.fileExists(atPath: documentsPath.path) {\n            try? fm.removeItem(at: documentsPath)\n        }\n        try contents.write(to: documentsPath, atomically: true, encoding: .utf8)'''
        changed=m.patch_pairing_storage(test)
        self.assertNotIn('fm.removeItem(at: documentsPath)',changed)
        self.assertEqual(m.patch_pairing_storage(changed),changed)
    def test_PIN_is_not_logged(self):
        text='''debugLog("[WirelessPairService] gateway onPin callback (pin='\\(pinString)')")'''
        change=m.patch_wireless_log(text)
        self.assertNotIn('pinString)',change)
        self.assertIn('pin=redacted',change)
    def test_original_exact_source_verifier_accepts_only_v167_changes(self):
        import subprocess
        import tempfile
        from unittest.mock import patch as mock
        pinned=pathlib.Path(os.environ.get('EMBEDDED_SIDESTORE_TEST_SOURCE', '/tmp/v138-pinned/sidestore'))
        if not (pinned / '.git').exists():
            self.skipTest('pinned SideStore checkout is unavailable')
        import sys
        sys.path.insert(0,str(ROOT/'scripts'))
        try:
            import patch_v3_service as svc
            class Side:
                pass
            with tempfile.TemporaryDirectory() as temp:
                side=pathlib.Path(temp)
                adapters=(
                    ('AltStore/AppDelegate.swift',svc.headless_sidestore_app_delegate),
                    ('SideStore/Core/Auth/AuthManager.swift',
                     lambda src: svc.patch_auth_identity_generation(
                       svc.apply_embedded_credential_snapshot_patch(svc.headless_auth_manager(src), 'patch_auth_manager'))),
                    ('SideStore/Core/Auth/DeveloperPortalProxy.swift',svc.patch_developer_portal_proxy),
                    ('AltStore/Managing Apps/AppManager.swift',svc.headless_app_manager),
                    ('AltStore/Core/Model/RefreshAttempt.swift',svc.headless_refresh_attempt_error_privacy),
                    ('AltStore/Intents/App Intents/RefreshAllAppsIntent.swift',
                     lambda src: svc.headless_app_intents(src,'RefreshAllAppsIntent.swift')),
                    ('SideStore/AppBootManager.swift',svc.headless_app_boot_manager),
                    ('SideStore/Core/JIT/SideJITManager.swift',svc.headless_sidejit_manager),
                    ('SideStore/Core/Pairing/PairingFileManager.swift',svc.headless_pairing_file_manager),
                    ('SideStore/Handlers/PipelineHandler.swift',svc.headless_pipeline_handler),
                    ('SideStore/Core/Operations/StandaloneOperations/ClearAppCacheOperation.swift',svc.headless_clear_cache_operation),
                    ('SideStore/Views/Settings/Advanced/Connection/ConnectionConfig.swift',svc.headless_connection_config),
                    ('SideStore/Core/DeviceApi/MinimuxerWrapper.swift',svc.headless_minimuxer_connection_binding),
                )
                for relative,transform in adapters:
                    src=subprocess.check_output(['git','-C',str(pinned),'show',f'{svc.PINS[1]}:{relative}'],text=True)
                    expected=transform(src)
                    if relative=='AltStore/AppDelegate.swift':
                        expected=svc.replace(expected,
                            '                debugLog("Started DatabaseManager.")\n',
                            '                debugLog("Started DatabaseManager.")\n'
                            '                // V3_SIDESTORE_STATUS_SNAPSHOT_V1: retired in favor of live XPC reads.\n')
                        expected=svc.redact_external_url_logs(expected,relative)
                        expected=m.patch_service(m.patch_wire(expected))
                    elif relative=='SideStore/Core/Pairing/PairingFileManager.swift':
                        expected=m.patch_pairing_storage(expected)
                    f=side/relative
                    f.parent.mkdir(parents=True,exist_ok=True)
                    f.write_text(expected)
                generated=side/'SideStore/Core/DeviceApi/ConnectionConfig.swift'
                generated.parent.mkdir(parents=True,exist_ok=True)
                generated.write_text(svc.HEADLESS_BACKEND_CONNECTION_CONFIG+'\n')
                original_check_output=svc.subprocess.check_output
                def pinned_git(args,**kwargs):
                    if args[0:3]==['git','-C',str(side)]:
                        args=['git','-C',str(pinned),*args[3:]]
                    return original_check_output(args,**kwargs)
                with mock.object(svc.subprocess,'check_output',side_effect=pinned_git), \
                     mock.object(svc,'verify_headless_anisette_models',return_value=None):
                    svc.verify_headless_ui_adapters(side,svc.PINS[1])
                    tamper=side/'AltStore/AppDelegate.swift'
                    tamper.write_text(tamper.read_text()+'\n// unexpected legacy code\n')
                    with self.assertRaisesRegex(SystemExit,'exact pinned headless UI patch'):
                        svc.verify_headless_ui_adapters(side,svc.PINS[1])
        finally:
            sys.path.remove(str(ROOT/'scripts'))

    def test_running_source_boundaries(self):
        lc=os.getenv('V167_LIVE_ROOT')
        sidestore=os.getenv('V167_SIDESTORE_ROOT')
        if not lc or not sidestore:return
        l=pathlib.Path(lc);s=pathlib.Path(sidestore)
        for file,required in ((l/'LiveContainerSwiftUI/Views/V3UnifiedShell.swift','scarletV167OnDevicePair'),
                              (l/'SideStoreSupport/SideStore.swift','wirelessPairStart'),
                              (s/'AltStore/AppDelegate.swift','V3OriginalOnDevicePairingSession'),
                              (s/'SideStore/Core/Pairing/PairingFileManager.swift','SCARLET_V167_ATOMIC_PAIRING_PRESERVE'),
                              (s/'Dependencies/minimuxer/Sources/Services/WirelessPairService.swift','SCARLET_V167_PIN_LOG_REDACTION')):
            self.assertTrue(file.is_file(),file)
            self.assertIn(required,file.read_text())
if __name__=='__main__':unittest.main()
