import Foundation

@main
private struct FreeSevenDayPolicyContract {
    static func main() {
        let p=ScarletRefreshPolicy()
        let now=Date(timeIntervalSince1970: 1800000000)
        let expiry=now.addingTimeInterval(7*24*3600)
        let fresh=p.assess(now:now,profileExpiresAt:expiry)
        precondition(fresh.decision == .healthy)
        precondition(fresh.nextCheckAt == now.addingTimeInterval(12*3600))
        precondition(fresh.requiresAuthoritativeInstallResult)

        let near=p.assess(now:now,profileExpiresAt:now.addingTimeInterval(24*3600))
        precondition(near.decision == .refreshDue)
        precondition(near.nextCheckAt == now.addingTimeInterval(3600))

        let expired=p.assess(now:now,profileExpiresAt:now.addingTimeInterval(-1))
        precondition(expired.decision == .alreadyExpired)

        let missing=p.assess(now:now,profileExpiresAt:nil)
        precondition(missing.decision == .profileUnavailable)

        let onlySigned=ScarletRefreshReceipt(outcome:.signedButNotInstalled,
                                              newProfileExpiration:expiry,
                                              installedBundleVerified:false)
        precondition(!onlySigned.isRenewalComplete)
        let falselyClaimed=ScarletRefreshReceipt(outcome:.installedAndVerified,
                                                  newProfileExpiration:nil,
                                                  installedBundleVerified:true)
        precondition(!falselyClaimed.isRenewalComplete)

        let verified=ScarletRefreshReceipt(outcome:.installedAndVerified,
                                           newProfileExpiration:expiry,
                                           installedBundleVerified:true)
        precondition(verified.isRenewalComplete)
        print("[PASS] FREE_ACCOUNT_SEVEN_DAY_EXPIRY_NOT_BYPASSED")
        print("[PASS] AUTOMATIC_REFRESH_EARLY_WARNING_48H")
        print("[PASS] REFRESH_REQUIRES_DEVICE_INSTALLED_VERIFICATION")
    }
}
