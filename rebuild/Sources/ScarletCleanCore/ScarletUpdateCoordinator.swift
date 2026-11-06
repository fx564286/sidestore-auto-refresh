// Scarlet Crystal — free Personal Team update/refresh coordinator.
// Integration boundary only. The real, upstream SideStore/SideSign adapter
// must implement the three operations. No Apple credential or fake install.
import Foundation

public struct ScarletUpdateState: Sendable {
    public let installedBuild: Int
    public let publishedBuild: Int
    public let hoursToProfileExpiry: Double
    public let appGroupAndIdentityValid: Bool
    public let serviceConnected: Bool
    public let authenticated: Bool
    public let paired: Bool
    public let signedReleaseVerified: Bool

    public init(installedBuild: Int, publishedBuild: Int,
                hoursToProfileExpiry: Double,
                appGroupAndIdentityValid: Bool,
                serviceConnected: Bool, authenticated: Bool,
                paired: Bool, signedReleaseVerified: Bool) {
        self.installedBuild = installedBuild
        self.publishedBuild = publishedBuild
        self.hoursToProfileExpiry = hoursToProfileExpiry
        self.appGroupAndIdentityValid = appGroupAndIdentityValid
        self.serviceConnected = serviceConnected
        self.authenticated = authenticated
        self.paired = paired
        self.signedReleaseVerified = signedReleaseVerified
    }
}

public enum ScarletMaintenanceStatus: String, Sendable {
    case current
    case deferred
    case blocked
    case unverified
    case completed
}

public struct ScarletMaintenanceReceipt: Sendable {
    public let status: ScarletMaintenanceStatus
    public let reason: String
    public let requestedBuild: Int?
    public let installedBuildConfirmed: Bool
}

public protocol ScarletMaintenancePort: Sendable {
    // Must obtain an Apple-issued profile with all original App Group grants.
    // Returns true ONLY after 4 signed bundle profiles are actually verified.
    func refreshAndVerifyFourProfiles() async throws -> Bool
    // True only if SideStore/paired installer accepted same-bundle upgrade.
    func installVerifiedRelease(build: Int) async throws -> Bool
    // Independent query: installer acceptance does not prove installation.
    func confirmedInstalledBuild() async throws -> Int?
}

public actor ScarletUpdateCoordinator {
    private let port: any ScarletMaintenancePort
    private var working = false
    public static let refreshThresholdHours: Double = 72

    public init(port: any ScarletMaintenancePort) {
        self.port = port
    }

    public func maintain(_ input: ScarletUpdateState) async -> ScarletMaintenanceReceipt {
        func receipt(_ status: ScarletMaintenanceStatus,
                     _ reason: String, _ requested: Int? = nil,
                     _ confirmed: Bool = false) -> ScarletMaintenanceReceipt {
            ScarletMaintenanceReceipt(status: status, reason: reason,
                                      requestedBuild: requested,
                                      installedBuildConfirmed: confirmed)
        }
        guard !working else { return receipt(.deferred, "maintenance_in_progress") }
        guard input.installedBuild > 0, input.publishedBuild >= input.installedBuild,
              input.hoursToProfileExpiry.isFinite else {
            return receipt(.blocked, "invalid_build_or_expiry_state")
        }
        guard input.appGroupAndIdentityValid else {
            return receipt(.blocked, "app_group_or_bundle_identity_missing")
        }
        let refreshDue = input.hoursToProfileExpiry <= Self.refreshThresholdHours
        let hasUpdate = input.publishedBuild > input.installedBuild
        guard refreshDue || hasUpdate else {
            return receipt(.current, "current_and_not_expiring", nil, true)
        }
        guard input.serviceConnected, input.authenticated, input.paired else {
            // Apple 2FA and device trust cannot be silently manufactured.
            return receipt(.blocked, "sidestore_auth_or_pairing_unavailable")
        }
        guard !hasUpdate || input.signedReleaseVerified else {
            return receipt(.deferred, "new_release_not_signed_and_verified",
                           input.publishedBuild)
        }
        working = true
        defer { working = false }
        do {
            if refreshDue {
                guard try await port.refreshAndVerifyFourProfiles() else {
                    return receipt(.unverified, "apple_profiles_not_verified")
                }
            }
            if hasUpdate {
                guard try await port.installVerifiedRelease(build: input.publishedBuild) else {
                    return receipt(.unverified, "upgrade_not_accepted",
                                   input.publishedBuild)
                }
                let observed = try await port.confirmedInstalledBuild()
                guard observed == input.publishedBuild else {
                    return receipt(.unverified, "installed_build_not_confirmed",
                                   input.publishedBuild)
                }
                return receipt(.completed, "installed_build_verified",
                               input.publishedBuild, true)
            }
            // Refreshing provisioning may not install the app! The SideStore
            // adapter must handle its actual re-sign/reinstall cycle.
            let observed = try await port.confirmedInstalledBuild()
            guard observed == input.installedBuild else {
                return receipt(.unverified, "refresh_reinstall_not_confirmed")
            }
            return receipt(.completed, "refresh_and_installed_build_verified",
                           input.installedBuild, true)
        } catch {
            // Apple auth/2FA or SideStore install failures remain visible.
            return receipt(.unverified, "apple_refresh_or_install_failed")
        }
    }
}
