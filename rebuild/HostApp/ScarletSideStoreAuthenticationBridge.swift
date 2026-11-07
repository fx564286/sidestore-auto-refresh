// Scarlet's own login UI delegates authentication to the pinned SideStore
// worker over an authenticated-to-the-extension anonymous XPC endpoint.
import Foundation
import SideStoreSupport

@available(iOS 17.0, *)
@MainActor
final class ScarletConnectedSideSignEngine: ScarletAppleSignInEngine {
    var isReady: Bool { ScarletNativeAuthTransport.shared.isReady }

    func prepare() async throws {
        try await ScarletNativeAuthTransport.shared.prepare()
    }

    func signIn(appleID: String, password: String,
                anisetteProfile: String,
                 requestTwoFactorCode: @escaping @MainActor () async throws -> String) async throws {
        do {
            try await ScarletNativeAuthTransport.shared.signIn(
                email: appleID, password: password,
                anisetteProfile: anisetteProfile,
                codeProvider: requestTwoFactorCode)
        } catch let error as ScarletNativeAuthError {
            // NSError bridging of a Swift enum collapses failures to code 0.
            // Emit only the actual remote domain/code. Never emit credentials,
            // OTPs, headers, request IDs or arbitrary NSError.userInfo.
            switch error {
            case .remoteFailure(let domain, let code):
                ScarletDiagnosticRecorder.shared.record(
                    "auth", "remote_failure", status: "error",
                    fields: ["stage": "sidestore_signin",
                             "domain": domain, "code": String(code)])
            case .guestUnavailable:
                ScarletDiagnosticRecorder.shared.record(
                    "auth", "guest_unavailable", status: "error")
            case .workerUnavailable:
                ScarletDiagnosticRecorder.shared.record(
                    "auth", "worker_unavailable", status: "error")
            case .alreadyRunning:
                ScarletDiagnosticRecorder.shared.record(
                    "auth", "already_running", status: "blocked")
            case .timedOut:
                ScarletDiagnosticRecorder.shared.record(
                    "auth", "request_timeout", status: "error")
            }
            throw error
        }
    }

    func cancel() {
        ScarletNativeAuthTransport.shared.cancel()
    }
}
