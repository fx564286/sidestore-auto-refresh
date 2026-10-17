"""V24 regressions: retries for spurious -999; never repeat user cancellations."""
from pathlib import Path
import importlib.util
import os
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "v24_patch", ROOT / "scripts/patch_v24_install_download.py"
)
PATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PATCH)

class V24IPAInstallRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source_root = os.getenv("SIDESTORE_TEST_SOURCE") or os.getenv("EMBEDDED_SIDESTORE_TEST_SOURCE")
        if not source_root:
            raise unittest.SkipTest("Pinned SideStore source not supplied")
        cls.upstream = Path(source_root) / "SideStore/Core/Operations/StandaloneOperations/DownloadAppOperation.swift"
        if not cls.upstream.is_file():
            raise unittest.SkipTest("Pinned upstream downloader unavailable")

    def test_bounded_retry_and_true_cancellation(self):
        with tempfile.TemporaryDirectory(prefix="v24-ipa-recovery-") as temp:
            target=Path(temp)/"SideStore/Core/Operations/StandaloneOperations"
            target.mkdir(parents=True)
            source=target/"DownloadAppOperation.swift"
            shutil.copyfile(self.upstream, source)
            PATCH.patch(Path(temp))
            first=source.read_text(encoding="utf-8")
            self.assertIn("if realCancellation {\n                    throw OperationError.cancelled",first)
            self.assertIn("if transient && attempt < 3",first)
            self.assertIn("NSURLErrorCancelled",first)
            self.assertIn("NSURLErrorTimedOut",first)
            self.assertIn("configuration.waitsForConnectivity = true",first)
            self.assertIn("domain=\\(nsError.domain) code=\\(nsError.code)",first)
            self.assertEqual(first.count("func downloadFile(from downloadURL:"),1)
            PATCH.patch(Path(temp))
            self.assertEqual(first,source.read_text(encoding="utf-8"), "patch must be idempotent")

    def test_unrelated_download_path_is_untouched(self):
        with tempfile.TemporaryDirectory(prefix="v24-ipa-recovery-") as temp:
            target=Path(temp)/"SideStore/Core/Operations/StandaloneOperations"
            target.mkdir(parents=True)
            source=target/"DownloadAppOperation.swift"
            shutil.copyfile(self.upstream,source)
            before=source.read_text()
            marker="    private func downloadDependencies(for appBundle: ALTApplication)"
            self.assertIn(marker,before)
            PATCH.patch(Path(temp))
            after=source.read_text()
            self.assertEqual(before[before.index(marker):],after[after.index(marker):])

if __name__=="__main__":
    unittest.main()
