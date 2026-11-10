// Scarlet Crystal automatic SideStore refresh: foreground catch-up + native
// iOS BGAppRefreshTask. Scheduling is best effort under Apple's execution
// policy; the result is NOT proof of a newly installed provisioning profile.
import Foundation
import BackgroundTasks
import SideStoreSupport

// SideStore wraps very different internal failures in domain SideStore,
// code 1. Classify ONLY known constant phrases from the upstream native
// implementation; raw NSError descriptions can contain private user data.
@available(iOS 17.0, *)
enum ScarletRefreshFailureDiagnosis {
    static func category(_ error: Error) -> String {
        let e = error as NSError
        guard e.domain == "SideStore" else {
            return e.domain == NSCocoaErrorDomain
                ? "system_io_failure" : "native_refresh_unknown_error"
        }
        let description = e.localizedDescription.lowercased()
        if description.contains("another refresh task is in progress") {
            return "refresh_already_running"
        }
        if description.contains("unable to locate liveprocess bundle") {
            return "liveprocess_missing"
        }
        if description.contains("failed to start extension") {
            return "liveprocess_start_failed"
        }
        if description.contains("built-in sidestore quit unexpectedly") {
            return "embedded_sidestore_exited"
        }
        if description.contains("failed to start in reasonable time") {
            return "embedded_sidestore_start_timeout"
        }
        return "sidestore_internal_failure"
    }

    static func nativeGuidance(_ reason: String) -> String {
        switch reason {
        case "no_managed_apps":
            return "내장 SideStore에 관리 앱이 없습니다. 현재 Scarlet은 갱신 대상으로 등록되지 않았습니다."
        case "host_not_managed":
            return "내장 SideStore 데이터베이스에 현재 설치된 Scarlet 번들 ID가 등록되지 않았습니다. 다른 설치 프로그램의 앱은 자동으로 갱신 대상에 포함되지 않습니다."
        case "sidestore_certificate_missing":
            return "LiveContainer 인증서와 별개로 내장 SideStore 서명 인증서가 없습니다. SideStore 인증서 복구·가져오기 상태를 확인해야 합니다."
        case "sidestore_database_unavailable":
            return "내장 SideStore 설치 앱 데이터베이스 초기화가 실패했습니다."
        case "refresh_worker_missing":
            return "내장 SideStore LiveProcess에 갱신 확인 작업자가 연결되지 않았습니다."
        case "transport_unavailable", "transport_unresponsive":
            return "내장 SideStore LiveProcess의 XPC 연결을 확인하지 못했습니다."
        case "already_running":
            return "다른 SideStore 갱신 작업이 실행 중입니다."
        case "vpn_unavailable":
            return "갱신 중 SideStore가 필요한 VPN 또는 WireGuard 연결을 사용할 수 없습니다."
        case "anisette_unavailable":
            return "SideStore 갱신 중 Anisette 인증 정보 수신이 실패했습니다."
        case "server_unavailable":
            return "SideStore 설치 서버에 연결하지 못했습니다."
        case "signing_failed":
            return "SideStore의 서명 작업이 실패했습니다. 인증서 및 권한 상태를 확인해야 합니다."
        case "profile_refresh_failed":
            return "Apple 프로비저닝 프로파일 갱신 작업이 실패했습니다."
        case "installation_failed":
            return "서명 후 iPhone 앱 설치 단계가 실패했습니다."
        case "sidestore_native_operation_failed":
            return "SideStore 원본 AppManager 갱신 작업이 실패했습니다. 갱신 결과 로그를 확인하세요."
        case "worker_unresponsive":
            return "SideStore의 갱신 작업자에서 종료 응답을 받지 못했습니다."
        default:
            return "내장 SideStore의 관리 앱·인증서 상태를 확인하지 못했습니다."
        }
    }

    static func guidance(_ category: String) -> String {
        switch category {
        case "refresh_already_running":
            return "다른 갱신 작업이 진행 중입니다. 중복 실행 여부를 확인하세요."
        case "liveprocess_missing":
            return "LiveProcess 확장을 설치본에서 찾지 못했습니다. 확장을 유지한 서명·설치가 필요합니다."
        case "liveprocess_start_failed":
            return "LiveProcess 확장을 시작하지 못했습니다. 확장 서명과 프로비저닝 권한을 확인하세요."
        case "embedded_sidestore_exited":
            return "내장 SideStore 실행 프로세스가 종료됐습니다. SideStore 실행 오류 진단이 필요합니다."
        case "embedded_sidestore_start_timeout":
            return "내장 SideStore 실행 응답이 시간 내에 도착하지 않았습니다."
        default:
            return "내장 SideStore 갱신 단계가 실패했습니다. 인증서 존재만으로 설치 갱신을 보장할 수 없습니다."
        }
    }
}

@available(iOS 17.0, *)
@MainActor
final class ScarletAutomaticRenewal {
    static let shared = ScarletAutomaticRenewal()
    static let identifier = "com.kdt.livecontainer.P8EZT3U5N4.refresh"
    private let attemptKey = "Scarlet.Refresh.LastAttemptAt"
    private let outcomeKey = "Scarlet.Refresh.LastAttemptOutcome"
    private let sourceKey = "Scarlet.Refresh.LastAttemptSource"
    private let failureReasonKey = "Scarlet.Refresh.LastFailureReason"
    private func notifyStateChanged() {
        NotificationCenter.default.post(
            name: Notification.Name("ScarletRefreshOutcomeChanged"), object: nil)
    }
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
            let requestReturned = await refreshIfDue(origin: "background")
            // BG task completion is NOT a provisioning renewal receipt.
            // Previously even a thrown SideStore error was reported to iOS
            // as a completed-successful background refresh.
            let taskSucceeded = requestReturned && !Task.isCancelled
            bg.setTaskCompleted(success: taskSucceeded)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_background_task_completed",
                status: taskSucceeded ? "info" : "warning",
                fields: ["result": taskSucceeded ? "request_returned" : "request_failed"])
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

    @discardableResult
    private func refreshIfDue(origin: String) async -> Bool {
        guard !running else { return false }
        let prefs = UserDefaults.standard
        let now = Date()
        if let last = prefs.object(forKey: attemptKey) as? Date,
           now.timeIntervalSince(last) < interval { return true }
        running = true
        defer { running = false; scheduleNext(); notifyStateChanged() }

        prefs.set(now, forKey: attemptKey)
        prefs.set(now, forKey: "Scarlet.Refresh.LastAttemptStartedAt")
        prefs.set(origin, forKey: sourceKey)
        prefs.set("요청 중 · 검증 전", forKey: outcomeKey)
        prefs.removeObject(forKey: failureReasonKey)
        notifyStateChanged()
        ScarletDiagnosticRecorder.shared.record(
            "refresh", "automatic_attempt_started",
            fields: ["result": origin])

        let gate = ScarletSigningReadiness.inspect()
        guard gate.canRequestNativeRefresh else {
            prefs.set("차단 · App Group 또는 서명 권한 불일치", forKey: outcomeKey)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_attempt_blocked", status: "blocked",
                fields: ["reason": gate.safeBlockCategory])
            prefs.set(gate.safeBlockCategory, forKey: failureReasonKey)
            return false
        }
        guard await ScarletConnectedSideSignEngine().storedAuthenticated() else {
            prefs.set("차단 · SideStore 로그인 세션 없음", forKey: outcomeKey)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_attempt_blocked", status: "blocked",
                fields: ["reason": "auth_unavailable"])
            prefs.set("auth_unavailable", forKey: failureReasonKey)
            return false
        }
        guard !Task.isCancelled else {
            prefs.set("중단 · 갱신 요청 취소됨", forKey: outcomeKey)
            return false
        }
        // Login and LC P12 were insufficient preflights: the embedded
        // SideStore has its own installed-app DB and signing Keychain.
        let nativeState = await ScarletNativeRefreshInspector.inspect()
        ScarletDiagnosticRecorder.shared.record(
            "refresh", "automatic_managed_apps_inspected",
            status: nativeState.canRefreshHost ? "success" : "blocked",
            fields: ["count": String(nativeState.count),
                     "host_managed": nativeState.hostManaged ? "true" : "false",
                     "signing_ready": nativeState.signingReady ? "true" : "false",
                     "reason": nativeState.reason])
        guard nativeState.canRefreshHost else {
            prefs.set("차단 · 내장 SideStore 관리 앱·인증서 확인 필요",
                      forKey: outcomeKey)
            prefs.set(nativeState.reason, forKey: failureReasonKey)
            return false
        }
        do {
            // Calls the pinned SideStore native signing+installation workflow.
            // This may return with no registered apps. Do not claim success.
            let receipt = try await ScarletNativeRefreshExecutor.execute()
            prefs.set("요청 반환 · 설치 상태 미검증", forKey: outcomeKey)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_native_worker_returned",
                fields: ["reason": receipt,
                         "installation_verified": "false"])
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_intent_returned",
                fields: ["installation_verified": "false"])
            return true
        } catch {
            let reason = (error as? ScarletNativeRefreshFailure)?.reason ??
                ScarletRefreshFailureDiagnosis.category(error)
            prefs.set("실패 · SideStore 갱신 오류", forKey: outcomeKey)
            prefs.set(reason, forKey: failureReasonKey)
            ScarletDiagnosticRecorder.shared.recordError(
                "refresh", "automatic_request_failed", error: error)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_failure_categorized",
                status: "error", fields: ["reason": reason])
            return false
        }
    }
}
