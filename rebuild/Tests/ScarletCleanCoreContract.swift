import Foundation

private struct SimulatedFailure: Error {}

private actor LocalSpy: ScarletLocalActionDriver {
    private var calls: [ScarletControl] = []
    func execute(_ action: ScarletControl) async throws { calls.append(action) }
    func called(_ action: ScarletControl) -> Int { calls.filter { $0 == action }.count }
}

private actor ServiceSpy: ScarletServiceActionDriver {
    private var calls: [ScarletControl] = []
    private var failing: Set<ScarletControl> = []
    func execute(_ action: ScarletControl) async throws {
        calls.append(action)
        if failing.contains(action) { throw SimulatedFailure() }
    }
    func fail(_ action: ScarletControl) { failing.insert(action) }
    func called(_ action: ScarletControl) -> Int { calls.filter { $0 == action }.count }
}

@main
private struct CleanCoreContract {
    static func main() async {
        let local = LocalSpy()
        let remote = ServiceSpy()
        let app = ScarletActionCoordinator(local: local, service: remote)

        // 1. Service outage must NOT disable native container settings.
        let initial = await app.tap(.localTapProbe)
        precondition(initial.state == .succeeded && initial.localTapCount == 1)
        precondition(await awaitValue({ await local.called(.localTapProbe) }) == 1)

        let preference = await app.tap(.localAppearance)
        precondition(preference.state == .succeeded)
        let notifications = await app.tap(.localClearNotifications)
        precondition(notifications.state == .succeeded)
        precondition(await awaitValue({ await local.called(.localClearNotifications) }) == 1)

        // 2. Service-driven controls fail closed and explain the reason.
        let blocked = await app.tap(.serviceReadSettings)
        precondition(blocked.state == .rejected &&
                     blocked.problem == .serviceUnavailable)
        precondition(await awaitValue({ await remote.called(.serviceReadSettings) }) == 0)
        precondition(blocked.message.contains("SideStore service unavailable"))

        // 3. Merely connecting does not grant Apple authentication.
        await app.updateAvailability(serviceReady: true, signedIn: false)
        let read = await app.tap(.serviceReadSettings)
        precondition(read.state == .succeeded)
        let login = await app.tap(.serviceBeginSignIn)
        precondition(login.state == .succeeded)
        let syncBlocked = await app.tap(.serviceSyncAppIDs)
        precondition(syncBlocked.problem == .signInRequired)
        precondition(await awaitValue({ await remote.called(.serviceSyncAppIDs) }) == 0)

        // 4. Authenticated service mutations call the service once.
        await app.updateAvailability(serviceReady: true, signedIn: true)
        let sync = await app.tap(.serviceSyncAppIDs)
        precondition(sync.state == .succeeded)
        precondition(await awaitValue({ await remote.called(.serviceSyncAppIDs) }) == 1)

        // 5. Unknown service errors never appear as successful installs.
        await remote.fail(.serviceInstallIPA)
        let install = await app.tap(.serviceInstallIPA)
        precondition(install.state == .failed &&
                     install.problem == .actionFailed)
        precondition(await awaitValue({ await remote.called(.serviceInstallIPA) }) == 1)

        // 6. Availability regressions do not poison local action routing.
        await app.updateAvailability(serviceReady: false, signedIn: true)
        let refreshBlocked = await app.tap(.serviceRefreshApp)
        precondition(refreshBlocked.problem == .serviceUnavailable)
        let localAgain = await app.tap(.localTapProbe)
        precondition(localAgain.state == .succeeded &&
                     localAgain.localTapCount == 2)

        // 7. Dependency classification covers EVERY public control.
        precondition(ScarletControl.allCases.count == 11)
        for action in ScarletControl.allCases {
            switch action.dependency {
            case .local, .service, .authenticatedService: break
            }
        }

        print("[PASS] SCARLET_CLEAN_CORE_LOCAL_CONTROLS_WORK_WITHOUT_SERVICE")
        print("[PASS] SCARLET_CLEAN_CORE_REMOTE_CONTROLS_EXPLAIN_UNAVAILABLE")
        print("[PASS] SCARLET_CLEAN_CORE_AUTH_STATE_IS_NOT_INFERRED_FROM_CONNECT")
        print("[PASS] SCARLET_CLEAN_CORE_NO_FALSE_INSTALL_SUCCESS_OR_REPLAY")
        print("[PASS] SCARLET_CLEAN_CORE_LOCAL_ISOLATION_AND_11_ACTION_CLASSES")
    }

    // The test is an async main; this helper keeps actor reads explicit.
    private static func awaitValue(_ read: () async -> Int) async -> Int {
        await read()
    }
}
