import Foundation

enum DeveloperPortalError: Error {
    case incorrectCredentials
    case appSpecificPasswordRequired
    case incorrectVerificationCode
    case tooManyAttempts
    case invalidAnisetteData
    case accountRepairRequired
    case userCancelled
    case authenticationHandshakeFailed
    case invalid2FAResponse
    case unknown
}

enum ServerError: Error {
    case badServerResponse(reason: String, jsonPayload: String)
    case invalidResponseFormat(rawPayload: String)
    case missingKey(key: String, jsonPayload: String)
    case underlyingError(code: Int, message: String)
}

enum SideSign {
    enum AnisetteError: Error {
        case noServersConfigured
        case allServersFailed
        case badServerResponse(statusCode: Int, payload: String)
    }
}



// Minimal typed dummies for the native SideStore error protocols used by
// v3SafeAuthCause. Keep this harness self-contained; production sources
// import their concrete definitions instead.
enum AnisetteKit {
    enum AnisetteError: Error {
        case readFailure, invalidArgument, loaderFailed, symbolMissing
        case invalidResponse, librariesNotFound
        case adiError(Int32, String)
        case httpError(Int, String)
    }
}

enum OperationError: Error {
    case notAuthenticated, noConnection, noVPN, invalidVPN
    case noDevice, notReachable, missingAppGroup, invalidPairingFile
    case pairingNotComplete
}

struct ALTWrappedError: Error { let wrappedError: Error }
struct V3SecretHandoffError: Error {}

@main
struct AuthErrorNuanceHarness {
    static func main() {
        let privateMarkers = ["PRIVATE_REASON", "PRIVATE_SERVER_BODY", "PRIVATE_RAW_PAYLOAD"]
        let ambiguousResponses: [ServerError] = [
            .badServerResponse(reason: "PRIVATE_REASON", jsonPayload: "PRIVATE_SERVER_BODY"),
            .invalidResponseFormat(rawPayload: "PRIVATE_RAW_PAYLOAD"),
            .missingKey(key: "Status", jsonPayload: "PRIVATE_SERVER_BODY")
        ]

        for error in ambiguousResponses {
            guard let kind = v3ClassifyAuthError(error) else {
                preconditionFailure("server response failures are not cancellation")
            }
            precondition(kind == .unknown, "response shape is not outage proof")
            let failure = CombinedFailure.capture(error, operation: "signIn",
                stage: .authentication, id: UUID().uuidString)
            var wire = failure.wire
            wire["kind"] = kind.rawValue
            precondition(v3HostAuthFailureMessage(from: wire)
                .contains("could not be safely classified"))
            let safeOutput = failure.technicalDetails + String(describing: wire) +
                v3HostAuthFailureMessage(from: wire)
            for marker in privateMarkers {
                precondition(!safeOutput.contains(marker), "provider details escaped safe output")
            }
        }

        precondition(v3ClassifyAuthError(DeveloperPortalError.incorrectCredentials) == .invalidCredentials)
        precondition(v3ClassifyAuthError(DeveloperPortalError.appSpecificPasswordRequired) == .appSpecificPasswordRequired)
        precondition(v3ClassifyAuthError(DeveloperPortalError.incorrectVerificationCode) == .invalidCode)
        precondition(v3ClassifyAuthError(DeveloperPortalError.tooManyAttempts) == .rateLimited)
        precondition(v3ClassifyAuthError(DeveloperPortalError.invalidAnisetteData) == .anisette)
        precondition(v3ClassifyAuthError(SideSign.AnisetteError.noServersConfigured) == .anisette)
        precondition(v3ClassifyAuthError(DeveloperPortalError.accountRepairRequired) == .accountRepairRequired)
        precondition(v3ClassifyAuthError(ServerError.underlyingError(
            code: -22411, message: "PRIVATE_RATE_LIMIT_BODY")) == .rateLimited)
        precondition(v3ClassifyAuthError(URLError(.networkConnectionLost)) == .network)
        precondition(v3ClassifyAuthError(DeveloperPortalError.userCancelled) == nil)
        precondition(v3ClassifyAuthError(URLError(.cancelled)) == nil)

        print("V3_AUTH_ERROR_NUANCE_PASS")
    }
}
