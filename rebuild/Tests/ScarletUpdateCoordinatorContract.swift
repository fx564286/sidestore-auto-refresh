import Foundation
private enum SimulatedError: Error { case fail }
private actor VerifiedInstaller: ScarletMaintenancePort {
    var refreshCalls=0
    var installCalls=0
    var accepted=true
    var actualBuild:Int?
    var profilesValid=true
    var throwsAuth=false
    func refreshAndVerifyFourProfiles() async throws -> Bool {
        refreshCalls+=1
        if throwsAuth { throw SimulatedError.fail }
        return profilesValid
    }
    func installVerifiedRelease(build:Int) async throws -> Bool {
        installCalls+=1
        return accepted
    }
    func confirmedInstalledBuild() async throws -> Int? {
        actualBuild
    }
    func setInstallResult(accepted:Bool,actual:Int?) {
        self.accepted=accepted;actualBuild=actual
    }
    func invalidateProfiles(){profilesValid=false}
    func require2FA(){throwsAuth=true}
    func counts()->(Int,Int){(refreshCalls,installCalls)}
}

@main struct TestScarletUpdater {
    static func state(_ installed:Int=204,_ published:Int=204,
                      _ hours:Double=90,_ valid:Bool=true,
                      _ connected:Bool=true,_ authenticated:Bool=true,
                      _ paired:Bool=true,_ signed:Bool=true)->ScarletUpdateState {
        ScarletUpdateState(installedBuild:installed,publishedBuild:published,
            hoursToProfileExpiry:hours,appGroupAndIdentityValid:valid,
            serviceConnected:connected,authenticated:authenticated,
            paired:paired,signedReleaseVerified:signed)
    }

    static func main() async {
        let driver=VerifiedInstaller()
        let c=ScarletUpdateCoordinator(port:driver)
        let current=await c.maintain(state())
        precondition(current.status == .current)
        let brokenGroup=await c.maintain(state(204,204,30,false))
        precondition(brokenGroup.status == .blocked &&
                     brokenGroup.reason == "app_group_or_bundle_identity_missing")
        let notAuthenticated=await c.maintain(state(204,204,30,true,true,false,true,true))
        precondition(notAuthenticated.status == .blocked)
        let noPairing=await c.maintain(state(204,204,30,true,true,true,false,true))
        precondition(noPairing.status == .blocked)
        let notSigned=await c.maintain(state(204,205,40,true,true,true,true,false))
        precondition(notSigned.status == .deferred)
        let firstCounts=await driver.counts()
        precondition(firstCounts.0==0 && firstCounts.1==0)

        await driver.setInstallResult(accepted:true,actual:204)
        let refreshed=await c.maintain(state(204,204,48))
        precondition(refreshed.status == .completed &&
                     refreshed.installedBuildConfirmed)
        let nextCounts=await driver.counts()
        precondition(nextCounts.0 == 1 && nextCounts.1 == 0)

        // Published release and signing freshness are distinct from
        // authoritative on-device install confirmation.
        let premature=await c.maintain(state(204,205,100))
        precondition(premature.status == .unverified &&
                     premature.reason == "installed_build_not_confirmed")
        await driver.setInstallResult(accepted:true,actual:205)
        let updated=await c.maintain(state(204,205,100))
        precondition(updated.status == .completed &&
                     updated.installedBuildConfirmed &&
                     updated.requestedBuild == 205)
        await driver.invalidateProfiles()
        let profileFailed=await c.maintain(state(205,205,10))
        precondition(profileFailed.status == .unverified &&
                     profileFailed.reason == "apple_profiles_not_verified")
        await driver.require2FA()
        let pending2FA=await c.maintain(state(205,205,10))
        precondition(pending2FA.status == .unverified &&
                     pending2FA.reason == "apple_refresh_or_install_failed")
        print("[PASS] REFRESH_72H_FREE_TEAM_NO_FALSE_PROFILE_SUCCESS")
        print("[PASS] UNAVAILABLE_AUTH_AND_PAIRING_ARE_FAIL_CLOSED")
        print("[PASS] RELEASE_ONLY_UPDATED_AFTER_AUTHORITATIVE_DEVICE_BUILD")
        print("[PASS] 2FA_AND_MISSING_APP_GROUP_NEVER_BYPASSED")
    }
}
