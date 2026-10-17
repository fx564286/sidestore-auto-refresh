#!/usr/bin/env python3
"""Patch the pinned SideStore IPA downloader to handle spurious -999 cancellations.

A true user/Task cancellation is never retried. Only a still-active operation
may retry transient URLSession cancellations/network interruptions, at most 3x.
No certificate, provisioning, JIT or account state is changed.
"""
from pathlib import Path
import sys

MARKER = "NRG_V24_INSTALL_DOWNLOAD_RECOVERY"

def patch(root: Path) -> None:
    path = root / "SideStore/Core/Operations/StandaloneOperations/DownloadAppOperation.swift"
    if not path.is_file():
        raise SystemExit(f"Missing SideStore download source: {path}")
    source = path.read_text(encoding="utf-8")
    if MARKER in source:
        verify(source)
        print("[PASS] V24 installer patch already present")
        return

    old_session = "    private let session = URLSession(configuration: .default)"
    new_session = """    // NRG_V24_INSTALL_DOWNLOAD_RECOVERY: allow large IPA transfers and
    // wait for brief connectivity changes without dropping app install state.
    private let session: URLSession = {
        let configuration = URLSessionConfiguration.default
        configuration.waitsForConnectivity = true
        configuration.timeoutIntervalForRequest = 120
        configuration.timeoutIntervalForResource = 600
        return URLSession(configuration: configuration)
    }()"""
    if source.count(old_session) != 1:
        raise SystemExit("Unexpected upstream URLSession declaration")
    source = source.replace(old_session, new_session, 1)

    start = source.find("    func downloadFile(from downloadURL: URL) async throws -> URL {")
    end = source.find("    private func downloadDependencies(for appBundle: ALTApplication)", start)
    if start < 0 or end < start or source.count("    func downloadFile(from downloadURL: URL) async throws -> URL {") != 1:
        raise SystemExit("Unexpected upstream downloadFile method")
    original_method = source[start:end]
    if original_method.count("try await self.session.download(from: downloadURL, delegate: delegate)") != 1:
        raise SystemExit("Unexpected upstream URLSession download call")

    replacement = """    func downloadFile(from downloadURL: URL) async throws -> URL {
        debugLog("[DownloadAppOperation] download started: \\(downloadURL.host ?? \"<local>\")")
        let delegate = DownloadProgressDelegate(progress: self.progress)
        for attempt in 1...3 {
            guard !self.isCancelled && !Task.isCancelled else {
                debugLog("[NRG_V24_INSTALL_DOWNLOAD_RECOVERY] cancelled_by_operation=true")
                throw OperationError.cancelled
            }
            do {
                let (fileURL, response) = try await self.session.download(from: downloadURL, delegate: delegate)
                if let response = response as? HTTPURLResponse {
                    debugLog("[DownloadAppOperation] download status=\\(response.statusCode) attempt=\\(attempt)")
                    guard response.statusCode != 403 else { throw URLError(.noPermissionsToReadFile) }
                    guard response.statusCode != 404 else {
                        throw CocoaError(.fileNoSuchFile, userInfo: [NSURLErrorKey: downloadURL])
                    }
                    guard (200..<300).contains(response.statusCode) else {
                        throw URLError(.badServerResponse)
                    }
                }
                self.setProgress(75)
                return fileURL
            } catch {
                let nsError = error as NSError
                let transientCodes: Set<Int> = [
                    NSURLErrorCancelled, NSURLErrorTimedOut,
                    NSURLErrorNetworkConnectionLost, NSURLErrorCannotConnectToHost
                ]
                let transient = nsError.domain == NSURLErrorDomain &&
                                transientCodes.contains(nsError.code)
                let realCancellation = self.isCancelled || Task.isCancelled
                // The original -999 must not be reclassified as proof of a user
                // cancellation. It is often a URLSession task cancellation.
                debugLog("[NRG_V24_INSTALL_DOWNLOAD_RECOVERY] stage=download attempt=\\(attempt) domain=\\(nsError.domain) code=\\(nsError.code) real_cancel=\\(realCancellation) transient=\\(transient)")
                if realCancellation {
                    throw OperationError.cancelled
                }
                if transient && attempt < 3 {
                    try await Task.sleep(nanoseconds: UInt64(attempt) * 2_000_000_000)
                    continue
                }
                throw error
            }
        }
        throw OperationError.unknown(failureReason: "The IPA download failed after retrying.")
    }

"""
    source = source[:start] + replacement + source[end:]
    verify(source)
    path.write_text(source, encoding="utf-8")
    print("[PASS] V24 IPA downloader patched; bounded retry and diagnostic correlation enabled")


def verify(source: str) -> None:
    required = [
        MARKER, "configuration.waitsForConnectivity = true",
        "configuration.timeoutIntervalForRequest = 120",
        "configuration.timeoutIntervalForResource = 600",
        "NSURLErrorCancelled", "NSURLErrorNetworkConnectionLost",
        "guard !self.isCancelled && !Task.isCancelled",
        "if realCancellation {", "if transient && attempt < 3",
        "Task.sleep(nanoseconds:", "domain=\\(nsError.domain) code=\\(nsError.code)"
    ]
    absent = [x for x in required if x not in source]
    if absent:
        raise SystemExit(f"V24 installer patch incomplete: {absent}")
    if source.count("func downloadFile(from downloadURL: URL)") != 1:
        raise SystemExit("Duplicate downloadFile implementation")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v24_install_download.py <embedded-sidestore-root>")
    patch(Path(sys.argv[1]))
