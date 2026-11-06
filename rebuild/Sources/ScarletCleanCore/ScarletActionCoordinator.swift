// Scarlet Crystal clean integration core.
// NEW implementation, independent of the legacy V3 service bridge.
// No App Group mutation, Apple login, keychain access, or UI styling here.
import Foundation

public enum ScarletControl: String, Codable, CaseIterable, Sendable {
    case localTapProbe
    case localClearNotifications
    case localAppearance
    case localStorageNavigation
    case localImportGuestIPA
    case localOpenEmbeddedSideStore

    case serviceReadSettings
    case serviceSetSettings
    case serviceReadLogs
    case serviceBeginSignIn

    case serviceSyncAppIDs
    case serviceRefreshApp
    case serviceInstallIPA

    public var dependency: ScarletDependency {
        switch self {
        case .localTapProbe, .localClearNotifications,
             .localAppearance, .localStorageNavigation,
             .localImportGuestIPA, .localOpenEmbeddedSideStore:
            return .local
        case .serviceReadSettings, .serviceSetSettings, .serviceReadLogs,
             .serviceBeginSignIn:
            return .service
        case .serviceSyncAppIDs, .serviceRefreshApp, .serviceInstallIPA:
            return .authenticatedService
        }
    }
}

public enum ScarletDependency: String, Sendable {
    case local
    case service
    case authenticatedService
}

public enum ScarletActionState: String, Codable, Sendable {
    case succeeded
    case rejected
    case failed
}

public enum ScarletActionProblem: String, Codable, Sendable {
    case serviceUnavailable
    case signInRequired
    case actionInProgress
    case actionFailed
}

public struct ScarletActionReceipt: Equatable, Sendable {
    public let action: ScarletControl
    public let state: ScarletActionState
    public let problem: ScarletActionProblem?
    public let localTapCount: Int

    public var message: String {
        switch problem {
        case .serviceUnavailable: return "SideStore service unavailable. Local settings remain usable."
        case .signInRequired: return "Sign in to SideStore before using this action."
        case .actionInProgress: return "This action is already running."
        case .actionFailed: return "The action failed. Recheck service state; no success was assumed."
        case nil: return "Action completed."
        }
    }
}

// Adapter protocols deliberately do not expose Apple credentials, device IDs,
// provisioning secrets or global mutable application state.
public protocol ScarletLocalActionDriver: Sendable {
    func execute(_ action: ScarletControl) async throws
}

public protocol ScarletServiceActionDriver: Sendable {
    func execute(_ action: ScarletControl) async throws
}

/// One actor owns admission, but a backend service may own its own operation
/// leases. Never clear or "repair" a remote lease from a button tap.
public actor ScarletActionCoordinator {
    private let local: any ScarletLocalActionDriver
    private let service: any ScarletServiceActionDriver
    // Explicitly optional. Diagnostics never send secrets or issue network calls.
    private let audit: ScarletControlAuditTrail?
    private var serviceReady = false
    private var signedIn = false
    private var inFlight: Set<ScarletControl> = []
    private var localTapCount = 0

    public init(local: any ScarletLocalActionDriver,
                service: any ScarletServiceActionDriver,
                audit: ScarletControlAuditTrail? = nil) {
        self.local = local
        self.service = service
        self.audit = audit
    }

    private func finalize(_ receipt: ScarletActionReceipt) async -> ScarletActionReceipt {
        if let audit { await audit.record(receipt) }
        return receipt
    }

    public func updateAvailability(serviceReady: Bool, signedIn: Bool) {
        self.serviceReady = serviceReady
        self.signedIn = serviceReady && signedIn
    }

    public func tap(_ action: ScarletControl) async -> ScarletActionReceipt {
        func receipt(_ state: ScarletActionState,
                     _ problem: ScarletActionProblem? = nil) -> ScarletActionReceipt {
            ScarletActionReceipt(action: action, state: state, problem: problem,
                                 localTapCount: localTapCount)
        }

        if inFlight.contains(action) {
            return await finalize(receipt(.rejected, .actionInProgress))
        }
        switch action.dependency {
        case .local: break
        case .service:
            guard serviceReady else { return await finalize(receipt(.rejected, .serviceUnavailable)) }
        case .authenticatedService:
            guard serviceReady else { return await finalize(receipt(.rejected, .serviceUnavailable)) }
            guard signedIn else { return await finalize(receipt(.rejected, .signInRequired)) }
        }

        // Claim the local admission key before the first await. Only the
        // matching action is fenced; a stalled XPC call cannot block a local tap.
        inFlight.insert(action)
        defer { inFlight.remove(action) }

        do {
            if action.dependency == .local {
                try await local.execute(action)
                if action == .localTapProbe { localTapCount += 1 }
            } else {
                try await service.execute(action)
            }
            return await finalize(receipt(.succeeded))
        } catch {
            // Do not promote unknown remote outcomes into success or retry
            // a signing/installation mutation automatically.
            return await finalize(receipt(.failed, .actionFailed))
        }
    }
}
