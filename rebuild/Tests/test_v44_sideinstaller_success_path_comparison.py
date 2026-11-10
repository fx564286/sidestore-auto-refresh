"""V44 structural regression: adapt proven RPPairing/AFC/install_proxy timeline.

This tests Swift source contract and the exact pinned SideStore source hook;
not a physical on-device installation. SideInstaller code is NOT copied.
"""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RP=(ROOT/"integration/ScarletGuestRefreshAgent.swift.txt").read_text()
INSTALL=(ROOT/"integration/ScarletDeviceInstallAgent.swift.txt").read_text()
WIRE=(ROOT/"integration/wire_scarlet_auth.py").read_text()
HOST=(ROOT/"HostApp/ScarletIntegratedHostView.swift").read_text()
DIAG=(ROOT/"HostApp/ScarletDiagnosticRecorder.swift").read_text()
WORKFLOW=(ROOT.parent/".github/workflows/scarlet-paired-engines-build.yml").read_text()

class SideInstallerReferencePath(unittest.TestCase):
    def test_uses_real_remote_rp_record_not_legacy_preferred_lockdown(self):
        self.assertIn('if #available(iOS 26.4, *) {', RP)
        self.assertIn('manager.fetchPairingFile(for: .rppairing)', RP)
        self.assertIn('manager.parse(content: rp, preferred: .rppairing)', RP)
        self.assertIn('parsed.mode == .rppairing', RP)
        self.assertIn('minimuxerPairingProtocol() == .rppairing', RP)
        self.assertIn('minimuxerStart(rp, preferred: .rppairing)', RP)
        self.assertIn('backend: .idevice', RP)
        self.assertIn('remotePairingPort: remotePairingPortCache', RP)
        self.assertIn('fetchUDID(forceLive: true)', RP)
        self.assertIn('rppairing_file_missing', RP + INSTALL)

    def test_post_sign_transport_check_is_inside_original_upstream_pipeline(self):
        self.assertIn('SideStore/Core/Operations/PipelineOperations/InstallAppOperation.swift', WIRE)
        self.assertIn('ScarletGuestDeviceTransport.ensurePostSignInstallTransport()', WIRE)
        hook=WIRE.index('ensurePostSignInstallTransport()')
        self.assertLess(hook, WIRE.index('if UserDefaults.standard.preferResignedIPA',hook))
        self.assertIn('if UserDefaults.standard.preferResignedIPA', WIRE)
        self.assertIn('install_pipeline_returned',WIRE)
        self.assertIn('ScarletDeviceInstallAgent.mark("afc_install_dispatched")',WIRE)
        self.assertIn('import Minimuxer', WIRE)
        self.assertIn('import MinimuxerCommon',WIRE)

    def test_rp_backend_is_shared_for_manual_install_and_refresh(self):
        self.assertIn('ScarletGuestDeviceTransport.ensureReady()',INSTALL)
        self.assertIn('ScarletGuestDeviceTransport.ensureReady()',RP)
        self.assertIn('try await ensureRPPairingReady()',RP)
        self.assertIn('AppManager.shared.install(.url(fileURL))',INSTALL)
        self.assertIn('AppManager.shared.backgroundRefresh(',RP)
        self.assertIn('CertificateManager.shared.loadActiveCertificate()',INSTALL)
        self.assertIn('ensureActiveTeamForRefresh()',INSTALL)
        self.assertNotIn('revokeCertificate(',INSTALL)
        self.assertNotIn('deletePairingFile(',INSTALL+RP)
        self.assertNotIn('requestCertificate(',INSTALL)

    def test_diagnostic_proves_where_failure_happened(self):
        for milestone in ('ipa_staged','certificate_loaded','team_verified',
                'rppairing_rsd_checked','appmanager_processing',
                'post_sign_transport_check','afc_install_dispatched',
                'install_pipeline_returned','appmanager_callback_returned'):
            self.assertIn(milestone,INSTALL+WIRE)
        self.assertIn('Scarlet.Install.LastStage.V44',INSTALL)
        self.assertIn('stageDefaults?.removeObject(forKey: stageKey)',HOST)
        self.assertIn('"worker_stage": lastWorkerStage',HOST)
        self.assertIn('"installation_verified": "false"',HOST)
        self.assertIn('"worker_stage"',DIAG)
        self.assertIn('rppairing_record_invalid',HOST)
        self.assertNotIn('fields: ["error": error.localizedDescription]',HOST)
        self.assertNotIn('Log pairing file bytes',WIRE)

    def test_no_liveprocess_virtual_fullscreen_regression(self):
        self.assertIn('try await app.runApp(multitask: false)',HOST)
        self.assertNotIn('ScarletResidentGuestMode.V41',HOST)
        self.assertNotIn('ScarletResidentGuestSwitchController',HOST)
        self.assertNotIn('MultitaskMode.virtualWindow',HOST)
        self.assertNotIn('ScarletResidentGuestSwitchController',WIRE)

    def test_release_v44(self):
        self.assertIn('fix/scarlet-v44-rppairing-postsign-install-20261111',WORKFLOW)
        self.assertIn('Scarlet-Crystal-V44-UNSIGNED.ipa',WORKFLOW)
        self.assertIn('scarlet-v44-unsigned-20261111',WORKFLOW)

if __name__=="__main__":
    unittest.main()
