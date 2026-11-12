"""R6P19 targeted regressions from dual R6P18 iPhone logs."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
HOST=(ROOT/'HostApp/ScarletIntegratedHostView.swift').read_text()
READINESS=(ROOT/'HostApp/ScarletSigningReadinessPanel.swift').read_text()

class DownloadEntitlementRegression(unittest.TestCase):
    def test_1005_retried_at_most_twice_with_bounded_waits(self):
        body=HOST.split('private func downloadSourceWithConnectionRecovery(',1)[1].split('// Source install routes',1)[0]
        self.assertIn('for attempt in 1...3',body)
        self.assertIn('ns.code == NSURLErrorNetworkConnectionLost',body)
        self.assertIn('attempt < 3',body)
        self.assertIn('attempt == 1 ? 400 : 1000',body)
        self.assertIn('try Task.checkCancellation()',body)
        self.assertIn('guest_download_connection_retry',body)
        self.assertIn('ns.code != NSURLErrorCancelled',body)

    def test_resume_data_used_without_fake_download_success(self):
        body=HOST.split('private func downloadSourceWithConnectionRecovery(',1)[1].split('// Source install routes',1)[0]
        self.assertIn('session.download(resumeFrom: resumeData)',body)
        self.assertNotIn('ns.code == NSURLErrorCannotResume',body)
        self.assertIn('ns.code != NSURLErrorCancelled',body)
        self.assertIn('session.download(from: url)',body)
        self.assertIn('NSURLSessionDownloadTaskResumeData',body)
        self.assertIn('throw error',body)
        self.assertIn('return try await session.download(from: url)',body)

    def test_original_download_validation_and_importer_remain(self):
        self.assertIn('downloadSourceWithConnectionRecovery(from: url, using: session)',HOST)
        self.assertIn('guard let http = response as? HTTPURLResponse',HOST)
        self.assertIn('guard magic == Data([0x50, 0x4B, 0x03, 0x04])',HOST)
        self.assertIn('handoffDownloadedSourceIfReady()',HOST)
        self.assertIn('try Task.checkCancellation()',HOST)
        self.assertIn('guest_download_failed',HOST)

    def test_entitlement_absent_must_not_advertise_p12_picker_as_repair(self):
        body=HOST.split('private func runGuest(',1)[1]
        self.assertIn('let signature = ScarletSigningReadiness.inspect()',body)
        self.assertIn('!signature.sideStoreAppGroupEntitled',body)
        self.assertIn('!signature.sideStoreAppGroupAccessible',body)
        self.assertIn('signature.safeBlockCategory',body)
        self.assertIn('서명에 SideStore App Group 권한이 없습니다',body)
        self.assertIn('인증서 재가져오기나 Apple 재로그인으로 복구할 수 없습니다',body)
        self.assertIn('jitless_signing_certificate_missing',body)

    def test_existing_signed_entitlement_criteria_unchanged(self):
        self.assertIn('SecTaskCopyValueForEntitlement(',READINESS)
        self.assertIn('com.apple.security.application-groups',READINESS)
        self.assertIn('FileManager.default.containerURL(',READINESS)
        self.assertIn('group.com.SideStore.SideStore.',READINESS)
        self.assertIn('P8EZT3U5N4',READINESS)
        self.assertNotIn('SecItemDelete(',HOST)

if __name__=='__main__':unittest.main()
