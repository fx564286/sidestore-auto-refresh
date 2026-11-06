import Foundation

private struct AuditFailure: Error {}

private actor LocalDriver: ScarletLocalActionDriver {
    func execute(_ action: ScarletControl) async throws {
        if action == .localAppearance { throw AuditFailure() }
    }
}

private actor RemoteDriver: ScarletServiceActionDriver {
    func execute(_ action: ScarletControl) async throws {
        if action == .serviceReadLogs { throw AuditFailure() }
    }
}

@main
private struct ControlAuditContract {
    static func main() async throws {
        let audit = ScarletControlAuditTrail(capacity: 3)
        let coordinator = ScarletActionCoordinator(
            local: LocalDriver(), service: RemoteDriver(), audit: audit)

        let noService = await coordinator.tap(.serviceReadSettings)
        precondition(noService.problem == .serviceUnavailable)

        let local = await coordinator.tap(.localTapProbe)
        precondition(local.state == .succeeded && local.localTapCount == 1)

        await coordinator.updateAvailability(serviceReady: true, signedIn: false)
        let noLogin = await coordinator.tap(.serviceInstallIPA)
        precondition(noLogin.problem == .signInRequired)

        let error = await coordinator.tap(.serviceReadLogs)
        precondition(error.state == .failed)

        let events = await audit.snapshot()
        precondition(events.count == 3) // bounded 3, first rotated out
        precondition(events[0].action == .localTapProbe)
        precondition(events[1].problem == .signInRequired)
        precondition(events[2].state == .failed)

        let data = try await audit.exportJSON()
        let content = String(decoding: data, as: UTF8.self)
        for secret in ["password", "Apple ID", "2FA", "certificate",
                       "privateKey", "github_pat_", "deviceUDID"] {
            precondition(!content.localizedCaseInsensitiveContains(secret))
        }
        precondition(content.contains("serviceReadLogs"))
        precondition(content.contains("actionFailed"))
        await audit.clear()
        let empty = await audit.snapshot()
        precondition(empty.isEmpty)
        print("[PASS] CONTROL_AUDIT_BOUNDED_NO_CREDENTIALS")
        print("[PASS] BUTTON_OUTCOME_SUCCESS_FAILURE_REJECTED_VISIBLE")
        print("[NOTICE] APP_HOST_MONITORING_NOT_WIRED_TO_IPHONE")
    }
}
