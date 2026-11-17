"""P100 source gate for recovering the specific dead native SideStore XPC worker."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[2]
SRC=(R/'rebuild/HostApp/ScarletAuthXPCSupport.swift').read_text()
W=(R/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

class NativeXPCRebind(unittest.TestCase):
    def test_single_flight_prepare_prevents_duplicate_extension_restart(self):
        section=SRC.split('public final class ScarletNativeAuthTransport',1)[1].split('public func storedAuthenticated()',1)[0]
        self.assertIn('private var preparingWorker: Task<Void, Error>?',section)
        self.assertIn('if let preparingWorker {',section)
        self.assertIn('try await self.prepareConnectedWorker()',section)
        self.assertIn('let operation = Task { @MainActor in',section)
        self.assertIn('defer { preparingWorker = nil }',section)
    def test_remote_xpc_health_verified_before_signing_authority(self):
        section=SRC.split('private func prepareConnectedWorker()',1)[1].split('public func storedAuthenticated()',1)[0]
        self.assertIn('await workerResponds(remote)',section)
        self.assertIn('scarletRetireFailedAuthGuest(expected: remote)',section)
        self.assertIn('try await RefreshHandler.shared.scarletEnsureAuthGuest()',section)
        self.assertIn('await workerResponds(recovered)',section)
        self.assertIn('isReady = true',section)
    def test_only_failed_same_remote_invalidated_when_no_refresh_or_launch(self):
        section=SRC.split('func scarletRetireFailedAuthGuest(',1)[1].split('func scarletEnsureAuthGuest()',1)[0]
        for check in ('c == nil, launchContinuation == nil',
                      '(connected as AnyObject) === (expected as AnyObject)',
                      'ownedExtension._kill(9)', 'client = nil', 'sideStorePid = 0', 'ext = nil'):
            self.assertIn(check,section)
        self.assertNotIn('SecItemDelete(',section)
    def test_interrupted_old_process_cannot_clear_replaced_new_client(self):
        section=SRC.split('func scarletEnsureAuthGuest()',1)[1].split('throw ScarletNativeAuthError.guestUnavailable\n    }',1)[0]
        self.assertIn('process.setRequestInterruptionBlock { [weak process]',section)
        self.assertIn('self.ext === interrupted',section)
        self.assertIn('self.client = nil',section)
        self.assertIn('self.sideStorePid = 0',section)
        self.assertIn('allowOrphanRebind: false',section)
        self.assertIn('orphan_worker_rebound_after_no_connection',section)
    def test_p100_own_binary_proof_and_distinct_version(self):
        for mark in ('--host-build-version 3.8.100', 'version="3.8.100"',
                     'scarlet-v48-r6p100-native-xpc-rebind-unsigned-20261117',
                     'Scarlet-Crystal-V48-R6P100-NATIVE-XPC-REBIND-UNSIGNED.ipa',
                     'b"stale_worker_retired_after_readiness_failure"',
                     'b"orphan_worker_rebound_after_no_connection"'):
            self.assertIn(mark,W)

if __name__=='__main__':unittest.main()
