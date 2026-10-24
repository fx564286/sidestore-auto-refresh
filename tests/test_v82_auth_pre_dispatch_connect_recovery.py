"""V82: service startup retry for new sign-in never replays an Apple RPC.

These are source-level guardrail tests; only device execution can establish
that native NSExtension startup is healthy on the installed iOS firmware.
"""
import re
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] /
          'scripts/templates/v3_service_bridge.swift')

class V82AuthConnectionRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SOURCE.read_text(encoding='utf8')
        cls.start = cls.text.index('SCARLET_V82_AUTH_PRE_DISPATCH_CONNECT')
        cls.retry = cls.text[cls.start:cls.text.index('if let connectedTicket', cls.start)]

    def test_only_pre_dispatch_new_sign_in_eligible(self):
        guard = self.retry.split('guard let failure', 1)[0]
        for essential in ('operation == "authBegin"', 'operationSessionID != nil',
                          'activeMutation == id', '!statusDispatchedRequestIDs.contains(id)'):
            self.assertIn(essential, guard)
        for forbidden in ('authRespond', 'authPoll', 'authRetryProvisioning',
                          'signOut', 'install', 'refresh'):
            self.assertNotIn(f'operation == "{forbidden}"', guard)

    def test_only_native_extension_launch_failures_trigger_connect_retry(self):
        for essential in ('failure.operation == "connect"',
                          'failure.stage == .extensionLaunch',
                          '(failure.code == .failed || failure.code == .interrupted)',
                          '(readOnlyReconnect || safePreDispatchAuthBegin)'):
            self.assertIn(essential, self.retry)
        self.assertEqual(self.retry.count('try await connect()'), 2)
        self.assertEqual(self.retry.count('try Task.checkCancellation()'), 2)
        self.assertIn('try await Task.sleep(nanoseconds: 300_000_000)', self.retry)
        self.assertNotIn('pending[id] = continuation', self.retry)
        self.assertNotIn('client.', self.retry)

    def test_retry_precedes_rpc_dispatch_and_session_setup(self):
        request = self.text.index('public func request(operation:')
        dispatch = self.text.index('pending[id] = continuation', request)
        self.assertLess(self.start, dispatch)
        self.assertLess(self.text.index('try await connect()', self.start), dispatch)
        self.assertLess(self.text.index('if let connectedTicket', self.start), dispatch)

    def test_preserve_existing_hard_fail_and_safe_error_attribution(self):
        self.assertIn('else { throw error }', self.retry)
        end = self.text.index('let isBoundedSessionCreation', self.start)
        failure = self.text[self.start:end]
        self.assertIn('V3AuthAttemptStartFailurePolicy.confirmedNotDispatched',failure)
        self.assertIn('V3CatalogRequestContext.annotating',failure)

if __name__ == '__main__': unittest.main()
