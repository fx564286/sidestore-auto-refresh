"""P67: every post-auth failure must re-enter rollback, never return early."""
from pathlib import Path
import unittest
R=Path(__file__).resolve().parents[1]
A=(R/'integration/ScarletGuestSignInAgent.swift.txt').read_text()
V=(R/'integration/ScarletGuestSavedAccounts.swift.txt').read_text()
H=(R/'HostApp/ScarletAuthXPCSupport.swift').read_text()
W=(R.parent/'.github/workflows/scarlet-paired-engines-build.yml').read_text()
class P67Rollback(unittest.TestCase):
    def test_token_roundtrip_failure_throws_into_existing_inner_catch(self):
        section=A.split('guard persistedState() else {',1)[1].split('// R6P20:',1)[0]
        self.assertIn('throw NSError(domain: "scarlet.auth.keychain_roundtrip_failed"',section)
        self.assertNotIn('\n                    return\n',section)
        self.assertIn('if let previousSlot,',A)
        self.assertIn('!(await ScarletAccountVault.activate(previousSlot))',A)
        self.assertIn('throw NSError(domain: "scarlet.auth.rollback_unverified"',A)
    def test_vault_reports_failed_rollback_without_claiming_success(self):
        self.assertIn('if let previous, !(await activate(previous))',V)
        self.assertIn('return (false, "rollback_unverified")',V)
        self.assertIn('"rollback_unverified"]',H)
    def test_remote_failure_is_categorical_and_korean(self):
        self.assertIn('allowlisted.contains(failure.domain)',A)
        self.assertIn('case "scarlet.auth.rollback_unverified":',H)
        self.assertIn('이전 계정 복원 결과를 확인하지 못했습니다.',H)
    def test_p67_has_newer_bundle_version_than_p66(self):
        for marker in ('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.67)',
                       'Scarlet-Crystal-V48-R6P67-AUTH-ROLLBACK-UNSIGNED.ipa',
                       'scarlet-v48-r6p67-auth-rollback-unsigned-20261115',
                       'asset=Scarlet-Crystal-V48-R6P67-AUTH-ROLLBACK-UNSIGNED.ipa',
                       'asset=Scarlet-Crystal-V48-R6P66-MULTI-ACCOUNT-UNSIGNED.ipa'):
            self.assertIn(marker,W)
if __name__ == '__main__':unittest.main()
