// Scarlet Crystal free Personal Team provisioning refresh policy.
// Apple's 7-day validity does NOT change; this selects safe, proactive work.
import Foundation

public enum ScarletRefreshDecision: String, Sendable {
    case healthy
    case refreshDue
    case alreadyExpired
    case profileUnavailable
}

public struct ScarletRefreshAssessment: Equatable, Sendable {
    public let decision: ScarletRefreshDecision
    public let remainingSeconds: TimeInterval?
    public let nextCheckAt: Date?
    // A valid profile expiration is NOT proof of installed app or auth success.
    public let requiresAuthoritativeInstallResult: Bool = true
}

public struct ScarletRefreshPolicy: Sendable {
    public static let recommendedLeadTime: TimeInterval = 48 * 3600
    public static let maxCheckInterval: TimeInterval = 12 * 3600

    public init() {}

    public func assess(now: Date, profileExpiresAt: Date?) -> ScarletRefreshAssessment {
        guard let expires = profileExpiresAt else {
            return ScarletRefreshAssessment(decision: .profileUnavailable,
                                            remainingSeconds: nil,
                                            nextCheckAt: now.addingTimeInterval(3600))
        }
        let remaining = expires.timeIntervalSince(now)
        if remaining <= 0 {
            return ScarletRefreshAssessment(decision: .alreadyExpired,
                                            remainingSeconds: remaining,
                                            nextCheckAt: now)
        }
        if remaining <= Self.recommendedLeadTime {
            return ScarletRefreshAssessment(decision: .refreshDue,
                                            remainingSeconds: remaining,
                                            nextCheckAt: now.addingTimeInterval(3600))
        }
        return ScarletRefreshAssessment(
            decision: .healthy,
            remainingSeconds: remaining,
            nextCheckAt: min(now.addingTimeInterval(Self.maxCheckInterval),
                             expires.addingTimeInterval(-Self.recommendedLeadTime))
        )
    }
}

public enum ScarletRefreshOutcome: String, Sendable {
    case pending
    case signingFailed
    case signedButNotInstalled
    case installedAndVerified
}

/// This is NOT the SideSign implementation. It records the authoritative
/// outcome provided by the unchanged SideStore/SideSign device adapter.
public struct ScarletRefreshReceipt: Equatable, Sendable {
    public let outcome: ScarletRefreshOutcome
    public let newProfileExpiration: Date?
    public let installedBundleVerified: Bool
    public var isRenewalComplete: Bool {
        outcome == .installedAndVerified &&
        installedBundleVerified &&
        newProfileExpiration != nil
    }
}
