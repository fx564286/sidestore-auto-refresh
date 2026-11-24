// Scarlet Crystal automatic SideStore refresh: foreground catch-up + native
// iOS BGAppRefreshTask. Scheduling is best effort under Apple's execution
// policy; the result is NOT proof of a newly installed provisioning profile.
import Foundation
import CryptoKit
import BackgroundTasks
import UIKit
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
        case "no_managed_apps_for_selected_team":
            return "현재 선택한 Apple 설치팀으로 등록된 관리 앱이 없습니다. 해당 팀으로 IPA를 설치한 뒤 갱신할 수 있습니다."
        case "managed_apps_inactive_for_selected_team":
            return "선택 계정에 관리 앱은 있지만 모두 비활성 상태입니다. 활성화하기 전에는 갱신 대상이 아닙니다."
        case "managed_apps_excluded_from_refresh_for_selected_team":
            return "선택 계정에 관리 앱이 있지만 SideStore의 원본 갱신 필터에서 제외됐습니다. 앱 활성 상태와 스토어 자격을 확인해야 합니다."
        case "selected_team_inventory_unavailable":
            return "선택 계정 관리 앱 목록 조회가 실패했습니다. 관리 앱이 0개라고 판단할 수 없습니다."
        case "selected_team_certificate_missing":
            return "현재 선택한 개발팀의 서명 인증서가 없습니다. 앱 설치의 설치팀 선택 화면에서 인증서를 준비하세요."
        case "selected_team_changed":
            return "요청 중 설치팀이 변경됐습니다. 선택한 계정을 확인하세요."
        case "host_registration_failed", "host_payload_cache_unavailable",
             "host_cached_bundle_mismatch", "host_team_record_missing":
            return "설치된 Scarlet 호스트를 SideStore 관리 저장소에 등록하지 못했습니다. 기존 설치본은 유지됩니다."
        case "host_bundle_path_unavailable", "host_signed_bundle_unavailable",
             "host_identity_mismatch":
            return "서명된 Scarlet 호스트 파일을 확인하지 못했습니다. 실제 설치된 앱과 서명 상태를 확인해야 합니다."
        case "host_selected_team_mismatch":
            return "현재 Apple 설치팀과 Scarlet 호스트의 기존 서명팀이 다릅니다. 호스트를 다른 팀으로 재서명하지 않습니다. 해당 호스트 서명팀의 계정에서만 호스트 갱신이 가능합니다."
        case "selected_account_owner_unverified":
            return "현재 선택한 Apple ID와 개발팀의 원본 SideStore 소유권을 확인할 수 없어 갱신을 중단했습니다. 기존 계정·인증서는 보존됩니다."
        case "team_operation_in_progress":
            return "다른 계정 전환 또는 서명 작업이 진행 중이어서 수동 갱신이 중단됐습니다."
        case "host_selected_team_certificate_missing":
            return "호스트를 서명한 Apple 팀의 인증서가 현재 SideStore에 없습니다."
        case "host_managed_owner_mismatch":
            return "설치된 Scarlet 호스트의 SideStore 기록이 다른 Apple ID·개발팀 소유입니다. 해당 기록을 현재 계정으로 덮어쓰지 않았습니다."
        case "host_managed_record_inactive":
            return "설치된 Scarlet 호스트가 현재 계정에 등록돼 있지만 비활성 상태입니다. 임의로 활성화하거나 다른 계정으로 변경하지 않았습니다."
        case "native_host_reinstall_owner_unverified":
            return "원본 SideStore가 설치본을 처리했지만 결과 앱의 Apple ID·서명팀 소유권이 확인되지 않았습니다. 갱신 성공으로 처리하지 않았습니다."
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
        case "pairing_file_missing":
            return "내장 SideStore에 저장된 기기 페어링 파일이 없습니다. 기존 설치 프로그램의 페어링과 별도로 SideStore 연결 설정이 필요합니다."
        case "pairing_invalid":
            return "내장 SideStore에 저장된 페어링 정보가 현재 기기와 일치하지 않습니다."
        case "minimuxer_not_started":
            return "내장 SideStore Minimuxer 기기 연결 엔진이 시작되지 않았습니다."
        case "device_network_unavailable":
            return "내장 SideStore가 기기 연결망을 사용할 수 없습니다. VPN 또는 원격 연결 설정을 확인해야 합니다."
        case "device_endpoint_unavailable", "device_identifier_unavailable":
            return "내장 SideStore에서 페어링된 iPhone 엔드포인트를 찾지 못했습니다."
        case "sidestore_auth_missing":
            return "내장 SideStore의 인증 토큰이 없거나 복원되지 않았습니다. Apple 로그인 상태를 확인해야 합니다."
        case "sidestore_team_mismatch":
            return "Apple 개발자 포털에서 현재 Scarlet 설치본을 서명한 개발팀를 확인하지 못했습니다. 다른 팀으로 자동 전환하지 않았습니다."
        case "sidestore_team_recovery_failed":
            return "Apple 로그인 토큰은 존재하지만 내장 SideStore의 활성 개발팀 복구가 실패했습니다. 계정·인증서 정보는 유지됩니다."
        case "sidestore_team_owner_unverified":
            return "선택 Apple ID와 활성 개발팀의 실제 소유권이 일치하지 않습니다. 인증서·관리 앱을 다른 계정에 연결하지 않았습니다."
        case "sidestore_team_identifier_collision":
            return "두 Apple ID가 같은 개발팀 식별자를 공유합니다. 현재 SideStore 데이터베이스는 팀 식별자가 고유하므로 계정별 소유권을 따로 저장할 수 없습니다."
        case "sidestore_account_identifier_collision":
            return "서로 다른 Apple ID가 동일한 계정 식별자로 기록되어 충돌했습니다. 기존 계정 정보를 덮어쓰지 않았습니다."
        case "certificate_expired":
            return "SideStore의 서명 인증서 유효기간이 만료된 것으로 보고됐습니다."
        case "certificate_revoked":
            return "SideStore의 서명 인증서가 취소된 것으로 보고됐습니다."
        case "profile_missing":
            return "갱신에 필요한 Apple 프로비저닝 프로파일을 찾지 못했습니다."
        case "app_group_missing":
            return "SideStore가 필요한 App Group 저장소에 접근하지 못했습니다."
        case "sidestore_invalid_configuration", "native_worker_creation_failed":
            return "SideStore 갱신 엔진의 실행 구성 또는 작업 생성이 실패했습니다."
        case "device_operation_timed_out":
            return "기기 연결 작업이 응답을 완료하지 못했습니다."
        case "host_not_in_refresh_results":
            return "내장 SideStore 갱신이 종료됐지만 Scarlet 자체의 재서명 결과가 없습니다. 실행 중인 앱 제외 또는 갱신 대상 누락을 확인해야 합니다."
        case "native_unknown_database_stage":
            return "원본 SideStore 관리 앱 데이터베이스 준비 도중 원인이 분류되지 않은 오류가 발생했습니다."
        case "native_unknown_team_stage":
            return "SideStore의 기존 개발팀 확인 단계에서 분류되지 않은 오류가 발생했습니다. 계정·인증서를 변경하지 않았습니다."
        case "native_unknown_transport_stage":
            return "SideStore 기기 전송 연결 준비 단계에서 분류되지 않은 오류가 발생했습니다. 기존 페어링은 유지됩니다."
        case "native_unknown_appmanager_stage":
            return "원본 SideStore AppManager 갱신·설치 단계에서 분류되지 않은 오류가 발생했습니다. 재서명이나 설치 성공은 확인되지 않았습니다."
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
    // R6P20: some signers keep the user's observed suffix-duplicated
    // Bundle ID. Register the BG task for the *actual signed host ID*,
    // not a hard-coded sibling which iOS may refuse. Both exact variants
    // are present in the generated Info.plist allow-list.
    static var identifier: String {
        let original = "com.kdt.livecontainer.P8EZT3U5N4"
        let actual = Bundle.main.bundleIdentifier ?? original
        let signedHost = ScarletSigningReadiness.inspect()
        guard signedHost.actualHostIdentity &&
              signedHost.signedApplicationIdentifierMatches else {
            return original + ".refresh" // original safe registration fallback
        }
        return actual + ".refresh"
    }
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
    // Interactive Settings owns the selected account and certificate workflow.
    // Defer automatic renewal without losing the explicit owner-switch request.
    private var settingsInteractionActive = false
    private var pendingVerifiedAccountSwitch = false
    private var lastCheckWasDeferred = false
    private var lastDeferredReportAt: Date?
    private var lastScheduledFor: Date?
    private var lastScheduleSubmitAt: Date?

    private var interval: TimeInterval {
        // No current worker outcome verifies every installed profile.
        // In-flight, returned, changed-host-only and failed receipts all
        // remain unresolved; do not assign them a six-hour success cooldown.
        return 2 * 3600
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
        let due = pendingVerifiedAccountSwitch ? Date() : (last?.addingTimeInterval(interval) ?? .now)
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

    func setSettingsInteractionActive(_ active: Bool) {
        let wasActive = settingsInteractionActive
        settingsInteractionActive = active
        if wasActive && !active && pendingVerifiedAccountSwitch {
            Task { @MainActor in await self.foregroundCatchUp() }
        }
    }

    func foregroundCatchUp() async {
        scheduleNext()
        _ = await refreshIfDue(origin:
            pendingVerifiedAccountSwitch ? "verified_account_switch" : "foreground")
    }

    func refreshAfterVerifiedAccountSwitch() async {
        // Do not claim the worker's native Team gate while the user is still
        // working on the selected account's certificate in Settings.
        pendingVerifiedAccountSwitch = true
        scheduleNext()
        _ = await refreshIfDue(origin: "verified_account_switch")
    }

    private func handle(_ bg: BGAppRefreshTask) {
        scheduleNext()
        let operation = Task { @MainActor in
            let requestReturned = await refreshIfDue(origin:
                pendingVerifiedAccountSwitch ? "verified_account_switch" : "background")
            // BG task completion is NOT a provisioning renewal receipt.
            // Previously even a thrown SideStore error was reported to iOS
            // as a completed-successful background refresh.
            let taskSucceeded = requestReturned && !Task.isCancelled
            bg.setTaskCompleted(success: taskSucceeded)
            let outcome = !taskSucceeded ? "request_failed"
                : self.lastCheckWasDeferred ? "skipped_not_due"
                : "request_returned"
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_background_task_completed",
                status: taskSucceeded ? "info" : "warning",
                fields: ["result": outcome,
                         "installation_verified": "false"])
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
        lastCheckWasDeferred = false
        guard !settingsInteractionActive || UIApplication.shared.applicationState == .background else {
            lastCheckWasDeferred = true
            ScarletDiagnosticRecorder.shared.record("refresh",
                "automatic_deferred_interactive_settings",
                fields: ["reason": "settings_account_work_active",
                         "installation_verified": "false"])
            return true
        }
        let prefs = UserDefaults.standard
        let now = Date()
        if origin != "verified_account_switch",
           let last = prefs.object(forKey: attemptKey) as? Date,
           now.timeIntervalSince(last) < interval {
            // The host's onAppear and scenePhase.active callbacks can both
            // invoke foregroundCatchUp within 100 ms. This is ONE deferral,
            // not two independent refresh attempts.
            let elapsed = now.timeIntervalSince(last)
            let remainingMinutes = Int(
                ceil(max(0, interval - elapsed) / 60))
            if lastDeferredReportAt.map({
                now.timeIntervalSince($0) >= 30
            }) ?? true {
                lastDeferredReportAt = now
                ScarletDiagnosticRecorder.shared.record(
                    "refresh", "automatic_attempt_deferred",
                    fields: ["reason": "retry_interval_not_elapsed",
                             "source": origin,
                             "retry_minutes": String(remainingMinutes),
                             "installation_verified": "false"])
            }
            // BGTask still completes normally when no retry was due,
            // but this cannot be reported as installation success.
            lastCheckWasDeferred = true
            return true
        }
        running = true
        if origin == "verified_account_switch" { pendingVerifiedAccountSwitch = false }
        defer { running = false; scheduleNext(); notifyStateChanged() }

        // Do not start the 2h retry cooldown until the real SideStore
        // operation is about to run. Missing pairing/login is a deferral,
        // not a completed app refresh attempt.
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
        let authState = await ScarletConnectedSideSignEngine().storedAuthenticationState()
        if case .unavailable(let reason) = authState {
            prefs.set("보류 · SideStore 로그인 상태 확인 필요", forKey: outcomeKey)
            prefs.set("auth_state_unavailable", forKey: failureReasonKey)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_deferred_auth_read", status: "blocked",
                fields: ["reason": reason, "installation_verified": "false"])
            return false
        }
        guard authState.isAuthenticated else {
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
        // Avoid launching the original SideStore refresh while its real
        // pairing record/Minimuxer transport is unavailable. A remembered
        // checkmark or Apple login alone cannot satisfy this prerequisite.
        let (paired, pairingReason) =
            await ScarletNativePairingInstaller.inspectForAutomaticRefresh()
        // P72: a 20s read timeout in the redundant UI/host preflight does
        // not prove the SideStore RSD pairing was revoked. The real native
        // AppManager/installation worker still revalidates pairing and
        // transport before any device mutation (and can reconnect RSD).
        // Only this inconclusive probe result may continue; an explicit
        // invalid/missing pairing outcome still blocks the refresh.
        let pairingProbeInconclusive = !paired &&
            pairingReason == "pairing_state_read_timeout"
        if pairingProbeInconclusive {
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_pairing_preflight_inconclusive",
                status: "warning", fields: [
                    "reason": pairingReason,
                    "next_gate": "native_sidestore_worker",
                    "installation_verified": "false"])
        }
        guard paired || pairingProbeInconclusive else {
            // Timeout/unresponsive transport is not evidence that the saved
            // pairing was revoked. The next 15-minute BG slot or foreground
            // activation may retry without deleting the original record.
            let transient = pairingReason == "pairing_state_read_timeout" ||
                pairingReason == "transport_unavailable" ||
                pairingReason == "pairing_saved_transport_unavailable"
            prefs.set(transient ? "보류 · 기기 연결 재확인 예정"
                                : "차단 · 페어링 연결 확인 필요", forKey: outcomeKey)
            prefs.set(pairingReason, forKey: failureReasonKey)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_deferred_pairing",
                status: "blocked", fields: ["reason": pairingReason])
            return false
        }
        // Login and LC P12 were insufficient preflights: the embedded
        // SideStore has its own installed-app DB and signing Keychain.
        let nativeState = await ScarletNativeRefreshInspector.inspect()
        ScarletDiagnosticRecorder.shared.record(
            "refresh", "automatic_managed_apps_inspected",
            status: nativeState.canRefreshSelectedTeam ? "success" : "blocked",
            fields: ["count": String(nativeState.count),
                     "host_managed": nativeState.hostManaged ? "true" : "false",
                     "signing_ready": nativeState.signingReady ? "true" : "false",
                     "reason": nativeState.reason])
        guard nativeState.canRefreshSelectedTeam else {
            prefs.set("차단 · 내장 SideStore 관리 앱·인증서 확인 필요",
                      forKey: outcomeKey)
            prefs.set(nativeState.reason, forKey: failureReasonKey)
            return false
        }
        // Settings may have opened while an awaited preflight was running.
        // A preflight is not authority to start a mutation after that change.
        guard !settingsInteractionActive || UIApplication.shared.applicationState == .background else {
            if origin == "verified_account_switch" { pendingVerifiedAccountSwitch = true }
            lastCheckWasDeferred = true
            prefs.set("보류 · 계정 설정 작업 중", forKey: outcomeKey)
            ScarletDiagnosticRecorder.shared.record("refresh",
                "automatic_deferred_interactive_settings",
                fields: ["reason": "settings_account_work_active",
                         "installation_verified": "false"])
            return true
        }
        let previousAttempt = prefs.object(forKey: attemptKey) as? Date
        prefs.set(Date(), forKey: attemptKey)
        ScarletInstalledProfileReadback.beginRequest(source: "automatic")
        do {
            // Calls the pinned SideStore native signing+installation workflow.
            // This may return with no registered apps. Do not claim success.
            let receipt = try await ScarletNativeRefreshExecutor.execute()
            let recordChecked = receipt ==
                "native_profile_date_advanced_install_unverified" ||
                receipt == "native_refresh_record_updated_install_unverified"
            prefs.set(recordChecked ? "갱신 기록 확인 · 설치 미확인"
                                   : "요청 반환 · 설치 상태 미검증",
                      forKey: outcomeKey)
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_native_worker_returned",
                fields: ["reason": receipt,
                         "installation_verified": "false"])
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "automatic_intent_returned",
                fields: ["installation_verified": "false"])
            return true
        } catch {
            ScarletInstalledProfileReadback.discardFailedRequest()
            let reason = (error as? ScarletNativeRefreshFailure)?.reason ??
                ScarletRefreshFailureDiagnosis.category(error)
            if reason == "team_operation_in_progress" || reason == "already_running" {
                // Native gate refusal occurs before any renewal; do not
                // consume a new two-hour attempt cooldown.
                if let previousAttempt { prefs.set(previousAttempt, forKey: attemptKey) }
                else { prefs.removeObject(forKey: attemptKey) }
                if origin == "verified_account_switch" { pendingVerifiedAccountSwitch = true }
                lastCheckWasDeferred = true
                prefs.set("보류 · 다른 서명 작업 진행 중", forKey: outcomeKey)
                prefs.set(reason, forKey: failureReasonKey)
                ScarletDiagnosticRecorder.shared.record("refresh",
                    "automatic_deferred_native_busy",
                    fields: ["reason": reason, "installation_verified": "false"])
                return true
            }
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

// V37: installed iOS bundle readback, not SideStore DB metadata.
// A changed embedded.mobileprovision SHA proves the installed *host bundle*
// contains a different profile after a new process launch. It does NOT
// prove refresh of every managed app, or a change of certificate/team.
@available(iOS 17.0, *)
@MainActor
enum ScarletInstalledProfileReadback {
    private static let beforeKey = "Scarlet.Refresh.PreviousInstalledProfileSHA.V37"
    private static let ownerKey = "Scarlet.Refresh.ProfileRequestProcess.V37"
    private static let sourceKey = "Scarlet.Refresh.ProfileRequestSource.V37"
    private static let requestTimeKey = "Scarlet.Refresh.ProfileRequestDate.V37"
    private static let processMarker = UUID().uuidString

    private static func installedDigest() -> String? {
        let profile = Bundle.main.bundleURL.appendingPathComponent(
            "embedded.mobileprovision", isDirectory: false)
        guard let data = try? Data(contentsOf: profile),
              !data.isEmpty else { return nil }
        return SHA256.hash(data: data)
            .map { String(format: "%02x", $0) }.joined()
    }

    static func beginRequest(source: String) {
        guard let digest = installedDigest() else {
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "installed_profile_readback_unavailable",
                status: "warning", fields: ["reason": "profile_not_readable"])
            return
        }
        let prefs = UserDefaults.standard
        prefs.set(digest, forKey: beforeKey)
        prefs.set(processMarker, forKey: ownerKey)
        prefs.set(source, forKey: sourceKey)
        prefs.set(Date(), forKey: requestTimeKey)
        ScarletDiagnosticRecorder.shared.record(
            "refresh", "installed_profile_before_request",
            fields: ["reason": "baseline_captured", "source": source])
    }

    static func discardFailedRequest() {
        let prefs = UserDefaults.standard
        guard prefs.string(forKey: ownerKey) == processMarker else { return }
        for key in [beforeKey, ownerKey, sourceKey, requestTimeKey] {
            prefs.removeObject(forKey: key)
        }
    }

    static func verifyNewProcess() {
        let prefs = UserDefaults.standard
        guard let before = prefs.string(forKey: beforeKey),
              let owner = prefs.string(forKey: ownerKey),
              owner != processMarker else { return }
        guard let after = installedDigest() else {
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "installed_profile_readback_unavailable",
                status: "warning", fields: ["reason": "profile_not_readable"])
            return
        }
        if after != before {
            prefs.set("앱 프로파일 변경 확인",
                      forKey: "Scarlet.Refresh.LastAttemptOutcome")
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "installed_profile_changed_after_request",
                status: "success",
                fields: ["result": "installed_host_profile_changed",
                         "installation_verified": "false"])
            for key in [beforeKey, ownerKey, sourceKey, requestTimeKey] {
                prefs.removeObject(forKey: key)
            }
        } else {
            // Same profile bytes do not prove an installation failure:
            // the native worker may have reused the original profile.
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "installed_profile_unchanged_after_request",
                status: "warning",
                fields: ["reason": "still_unverified",
                         "installation_verified": "false"])
        }
    }
}
