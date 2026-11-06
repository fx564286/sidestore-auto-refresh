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
                requestTwoFactorCode: @escaping @MainActor () async throws -> String) async throws {
        try await ScarletNativeAuthTransport.shared.signIn(
            email: appleID, password: password,
            codeProvider: requestTwoFactorCode)
    }

    func cancel() {
        ScarletNativeAuthTransport.shared.cancel()
    }
}
