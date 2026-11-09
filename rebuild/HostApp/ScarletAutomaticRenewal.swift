// Scarlet Crystal automatic SideStore refresh: foreground catch-up + native
// iOS BGAppRefreshTask. Scheduling is best effort under Apple's execution
// policy; the result is NOT proof of a newly installed provisioning profile.
import Foundation
import BackgroundTasks
import SideStoreSupport

@available(iOS 17.0, *)
@MainActor
final class ScarletAutomaticRenewal {
    static let shared = ScarletAutomaticRenewal()
    static let identifier = "com.kdt.livecontainer.P8EZT3U5N4.refresh"
    private let attemptKey = "Scarlet.Refresh.LastAttemptAt"
    private let outcomeKey = "Scarlet.Refresh.LastAttemptOutcome"
    private let sourceKey = "Scarlet.Refresh.LastAttemptSource"
    private var registered = false
    private var running = false
    private var lastScheduledFor: Date?
    private var lastScheduleSubmitAt: Date?

    private var interval: TimeInterval {
        let status = UserDefaults.standard.string(forKey: outcomeKey) ?? ""
        return status.hasPrefix("실패") || status.hasPrefix("차단")
            ? 2 * 3600 : 6 * 3600
    }

    func registerAtLaunch() {
        guard !registered else { return }
        registered = BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.identifier, using: nil
        ) { task in
            guard let bg = task as? BGAppRefreshTask else {
                task.setTaskCompleted(success: false)
                return
            }
            Task { @MainActor in self.handle(bg) }
        }
        ScarletDiagnosticRecorder.shared.record(
            "refresh", "automatic_background_registered",
            fields: ["result": registered ? "registered" : "unavailable"])
        scheduleNext()
    }

    func scheduleNext() {
        // Avoid repeatedly canceling a healthy iOS background refresh slot.
        guard registered else { return }
        let last = UserDefaults.standard.object(forKey: attemptKey) as? Date
        let due = last?.addingTimeInterval(interval) ?? .now
        let requestedStart = max(Date().addingTimeInterval(15 * 60), due)
        if let lastScheduledFor, let lastScheduleSubmitAt,
           abs(lastScheduledFor.timeIntervalSince(requestedStart)) < 60,
           Date().timeIntervalSince(lastScheduleSubmitAt) < 5 * 60 {
            return
        }
        let request = BGAppRefreshTaskRequest(identifier: Self.identifier)
        request.earliestBeginDate = requestedStart
        BGTaskScheduler.shared.cancel(taskRequestWithIdentifier: Self.identifier)
        do {
            try BGTaskScheduler.shared.submit(request)
            lastScheduledFor = requestedStart
            lastScheduleSubmitAt = Date()
            UserDefaults.standard.set("예약됨 · iOS 실행 시각은 미보장",
                                      forKey: "Scarlet.Refresh.BackgroundSchedule")
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_background_scheduled")
        } catch {
            UserDefaults.standard.set("예약 실패 · 앱 실행 시 재시도",
                                      forKey: "Scarlet.Refresh.BackgroundSchedule")
            ScarletDiagnosticRecorder.shared.recordError(
                "refresh", "automatic_schedule_failed", error: error)
        }
    }

    func foregroundCatchUp() async {
        scheduleNext()
        await refreshIfDue(origin: "foreground")
    }

    private func handle(_ bg: BGAppRefreshTask) {
        scheduleNext()
        let operation = Task { @MainActor in
            await refreshIfDue(origin: "background")
            bg.setTaskCompleted(success: !Task.isCancelled)
        }
        bg.expirationHandler = {
            operation.cancel()
            Task { @MainActor in
                ScarletDiagnosticRecorder.shared.record(
                    "refresh", "automatic_background_expired",
                    status: "warning", fields: ["reason": "system_time_limit"])
            }
        }
    }

    private func refreshIfDue(origin: String) async {
        guard !running else { return }
        let prefs = UserDefaults.standard
        let now = Date()
        if let last = prefs.object(forKey: attemptKey) as? Date,
           now.timeIntervalSince(last) < interval { return }
        running = true
        defer { running = false; scheduleNext() }

        prefs.set(now, forKey: attemptKey)
        prefs.set(origin, forKey: sourceKey)
        prefs.set("요청 중 · 검증 전", forKey: outcomeKey)
        ScarletDiagnosticRecorder.shared.record(
            "refresh", "automatic_attempt_started",
            fields: ["result": origin])

        let gate = ScarletSigningReadiness.inspect()
        guard gate.canRequestNativeRefresh else {
            prefs.set("차단 · App Group 또는 서명 권한 불일치", forKey: outcomeKey)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_attempt_blocked", status: "blocked",
                fields: ["reason": gate.safeBlockCategory])
            return
        }
        guard await ScarletConnectedSideSignEngine().storedAuthenticated() else {
            prefs.set("차단 · SideStore 로그인 세션 없음", forKey: outcomeKey)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_attempt_blocked", status: "blocked",
                fields: ["reason": "auth_unavailable"])
            return
        }
        guard !Task.isCancelled else { return }
        do {
            // Calls the pinned SideStore native signing+installation workflow.
            // This may return with no registered apps. Do not claim success.
            _ = try await RefreshAllAppsIntent().perform()
            prefs.set("요청 반환 · 설치 상태 미검증", forKey: outcomeKey)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_intent_returned",
                fields: ["installation_verified": "false"])
        } catch {
            prefs.set("실패 · SideStore 갱신 오류", forKey: outcomeKey)
            ScarletDiagnosticRecorder.shared.recordError(
                "refresh", "automatic_request_failed", error: error)
        }
    }
}
