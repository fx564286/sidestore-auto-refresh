// Native in-app certificate resolution over the already authenticated
// SideStore LiveProcess XPC endpoint. Never send PKCS#12 via URLs or logs.
import Foundation

@available(iOS 17.0, *)
@MainActor
public final class ScarletNativeCertificateTransport {
    public static let shared = ScarletNativeCertificateTransport()
    private var requestID: String?
    private var completion: CheckedContinuation<(Data, String), Error>?
    private init() {}

    public func obtain() async throws -> (Data, String) {
        guard requestID == nil else { throw ScarletNativeAuthError.alreadyRunning }
        try await ScarletNativeAuthTransport.shared.prepare()
        guard await ScarletNativeAuthTransport.shared.storedAuthenticated(),
              let remote = RefreshHandler.shared.client else {
            throw ScarletNativeAuthError.guestUnavailable
        }
        let id = UUID().uuidString
        requestID = id
        defer { requestID = nil; completion = nil }
        return try await withCheckedThrowingContinuation {
            (c: CheckedContinuation<(Data, String), Error>) in
            completion = c
            remote.scarletIssueCertificate(id)
            Task { @MainActor in
                try? await Task.sleep(for: .seconds(120))
                if self.requestID == id, let pending = self.completion {
                    self.completion = nil
                    pending.resume(throwing: ScarletNativeAuthError.timedOut)
                }
            }
        }
    }

    func finished(_ id: String, code: Int, domain: String,
                  archive: Data, password: String) {
        guard id == requestID, let pending = completion else { return }
        completion = nil
        if code == 0 && !archive.isEmpty && archive.count <= 64 * 1024 {
            pending.resume(returning: (archive, password))
        } else {
            pending.resume(throwing:
                ScarletNativeAuthError.remoteFailure(domain: domain, code: code))
        }
    }
}

extension RefreshHandler {
    @objc func scarletCertificateCompleted(
        _ requestID: String, code: Int, domain: String,
        certificateData: Data, password: String
    ) {
        if #available(iOS 17.0, *) {
            Task { @MainActor in
                ScarletNativeCertificateTransport.shared.finished(
                    requestID, code: code, domain: domain,
                    archive: certificateData, password: password)
            }
        }
    }
}
