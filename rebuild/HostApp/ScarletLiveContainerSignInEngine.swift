// Scarlet-owned UI to original SideStore backend over the existing
// LiveContainer SideStoreSupport anonymous NSXPC channel.
import Foundation
import SideStoreSupport

@available(iOS 17.0, *)
@MainActor
final class ScarletLiveContainerSignInEngine: ScarletAppleSignInEngine {
    var isReady: Bool {
        ScarletSideStoreAuthTransport.shared.isEnginePresent
    }

    func signIn(appleID: String, password: String,
                requestTwoFactorCode: @escaping @MainActor (String) async throws -> String) async throws {
        try await ScarletSideStoreAuthTransport.shared.signIn(
            appleID: appleID,
            password: password,
            requestCode: { prompt in try await requestTwoFactorCode(prompt) }
        )
    }
}
