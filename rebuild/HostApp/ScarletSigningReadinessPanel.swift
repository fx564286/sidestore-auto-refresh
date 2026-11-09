// Scarlet Crystal signing readiness + explicit manual SideStore refresh UI.
// The profile/App Group entitlements are Apple-issued, never toggled or forged.
// A refresh IPC acknowledgement is NOT proof that a signed app was installed.
import Foundation
import Security
import SwiftUI
import SideStoreSupport

@available(iOS 17.0, *)
struct ScarletSigningReadiness {
    let actualHostIdentity: Bool
    let signedApplicationIdentifierMatches: Bool
    let developerTeamEntitled: Bool
    let sideStoreAppGroupEntitled: Bool
    let sideStoreAppGroupAccessible: Bool
    let developmentProfile: Bool
    let liveContainerCertificatePresent: Bool
    let liveContainerPasswordPresent: Bool

    var canRequestNativeRefresh: Bool {
        actualHostIdentity && signedApplicationIdentifierMatches &&
        developerTeamEntitled && sideStoreAppGroupEntitled &&
        sideStoreAppGroupAccessible
    }

    static func inspect() -> ScarletSigningReadiness {
        let task = SecTaskCreateFromSelf(nil)
        let team = SecTaskCopyValueForEntitlement(
            task, "com.apple.developer.team-identifier" as CFString, nil)?
            .takeRetainedValue() as? String
        let declaredGroups = SecTaskCopyValueForEntitlement(
            task, "com.apple.security.application-groups" as CFString, nil)?
            .takeRetainedValue() as? [String] ?? []
        let isDevelopment = SecTaskCopyValueForEntitlement(
            task, "get-task-allow" as CFString, nil)?
            .takeRetainedValue() as? Bool ?? false
        let applicationID = SecTaskCopyValueForEntitlement(
            task, "application-identifier" as CFString, nil)?
            .takeRetainedValue() as? String
        let bundleID = Bundle.main.bundleIdentifier
        let baseBundleID = "com.kdt.livecontainer.P8EZT3U5N4"
        // The user's signer may append a team suffix to a preserved
        // bundle ID. Accept ONLY these two already-observed exact forms.
        // The signed application-identifier entitlement must ALSO match
        // the actual installed bundle ID and declared developer team.
        let approvedBundles = [
            baseBundleID,
            baseBundleID + ".P8EZT3U5N4"
        ]
        let approvedBundle = bundleID.map { approvedBundles.contains($0) } ?? false
        let signedIDMatches = team != nil && bundleID != nil &&
            applicationID == (team! + "." + bundleID!)

        // The selected SideStore group must be explicitly authorized.
        // UserDefaults(suiteName:) may otherwise silently fall back to
        // UserDefaults.standard in pinned LiveContainer; that is not consent.
        let expectedGroup = "group.com.SideStore.SideStore." + (team ?? "")
        let declared = team != nil && declaredGroups.contains(expectedGroup)
        let accessible = declared &&
            FileManager.default.containerURL(
                forSecurityApplicationGroupIdentifier: expectedGroup) != nil

        return ScarletSigningReadiness(
            actualHostIdentity: approvedBundle,
            signedApplicationIdentifierMatches: signedIDMatches,
            developerTeamEntitled: team == "P8EZT3U5N4",
            sideStoreAppGroupEntitled: declared,
            sideStoreAppGroupAccessible: accessible,
            developmentProfile: isDevelopment,
            liveContainerCertificatePresent: LCUtils.certificateData() != nil,
            liveContainerPasswordPresent:
                LCSharedUtils.certificatePassword() != nil
        )
    }

    var safeBlockCategory: String {
        if !actualHostIdentity { return "host_bundle_mismatch" }
        if !signedApplicationIdentifierMatches { return "signed_application_identifier_mismatch" }
        if !developerTeamEntitled { return "developer_team_entitlement_missing" }
        if !sideStoreAppGroupEntitled { return "sidestore_app_group_not_entitled" }
        if !sideStoreAppGroupAccessible { return "sidestore_app_group_inaccessible" }
        return "none"
    }
}

@available(iOS 17.0, *)
struct ScarletSigningReadinessPanel: View {
    @State private var readiness = ScarletSigningReadiness.inspect()
    @State private var authenticated: Bool? = nil
    @State private var refreshing = false
    @State private var statusMessage: String?

    private func inspect() {
        readiness = ScarletSigningReadiness.inspect()
        ScarletDiagnosticRecorder.shared.record("refresh", "preflight_checked",
            fields: [
                "result": readiness.canRequestNativeRefresh ? "ready" : "blocked",
                "reason": readiness.safeBlockCategory,
                "lc_cert_present": readiness.liveContainerCertificatePresent ? "true" : "false"
            ])
        Task { @MainActor in
            authenticated = await ScarletConnectedSideSignEngine().storedAuthenticated()
        }
    }

    private func requestManualRefresh() {
        guard !refreshing else { return }
        inspect()
        guard readiness.canRequestNativeRefresh else {
            statusMessage = "App Group 또는 서명 권한이 누락됐습니다. Apple이 발급한 프로비저닝 프로파일을 확인해야 합니다."
            return
        }
        refreshing = true
        statusMessage = "내장 SideStore에서 앱 새로고침을 요청하는 중입니다."
        Task { @MainActor in
            defer { refreshing = false }
            let verified = await ScarletConnectedSideSignEngine().storedAuthenticated()
            authenticated = verified
            guard verified else {
                statusMessage = "내장 SideStore 로그인 세션이 없습니다. 먼저 Apple ID 인증을 완료하세요."
                ScarletDiagnosticRecorder.shared.record("refresh", "manual_blocked",
                    status: "blocked", fields: ["reason": "auth_unavailable"])
                return
            }
            do {
                // Native upstream action; do not navigate to the guest SideStore.
                // It can refresh registered apps, but must not be taken as proof
                // this Scarlet host was re-signed and reinstalled.
                _ = try await RefreshAllAppsIntent().perform()
                statusMessage = "SideStore 새로고침 요청이 종료됐습니다. 실제 프로파일 만료일과 iPhone 설치 상태는 아직 별도 확인이 필요합니다."
                ScarletDiagnosticRecorder.shared.record("refresh", "manual_request_returned",
                    status: "info", fields: ["installation_verified": "false"])
                inspect()
            } catch {
                statusMessage = "SideStore 새로고침이 실패했습니다. 인증·페어링·프로파일을 진단 로그에서 확인하세요."
                ScarletDiagnosticRecorder.shared.record("refresh", "manual_request_failed",
                    status: "error", fields: ["reason": "sidestore_refresh_error"])
                ScarletDiagnosticRecorder.shared.recordError(
                    "refresh", "manual_request_underlying_error", error: error)
            }
        }
    }

    var body: some View {
        Section {
            LabeledContent("자동 갱신", value: "미연결 · 실행 안 됨")
            LabeledContent("수동 갱신", value: "내장 SideStore 엔진")
            LabeledContent("SideStore 로그인",
                           value: authenticated == nil ? "확인 중" :
                                  (authenticated == true ? "인증됨" : "인증 필요"))
            LabeledContent("앱 그룹 권한",
                           value: readiness.sideStoreAppGroupEntitled ?
                                  (readiness.sideStoreAppGroupAccessible ? "확인됨" : "접근 불가")
                                  : "프로파일 권한 없음")
            LabeledContent("개발 팀·앱 식별자",
                           value: readiness.developerTeamEntitled &&
                                  readiness.actualHostIdentity &&
                                  readiness.signedApplicationIdentifierMatches ?
                                  "실제 서명과 일치" : "서명 불일치 / 권한 차단")
            LabeledContent("LiveContainer 서명 인증서",
                           value: readiness.liveContainerCertificatePresent &&
                                  readiness.liveContainerPasswordPresent ? "존재" : "없음")
            Button("권한 상태 다시 검사", action: inspect)
                .accessibilityIdentifier("SCARLET_REFRESH_ENTITLEMENT_READBACK")
            Button(action: requestManualRefresh) {
                if refreshing {
                    ProgressView()
                } else {
                    Label("SideStore 수동 새로고침", systemImage: "arrow.clockwise")
                }
            }
            .disabled(refreshing || !readiness.canRequestNativeRefresh ||
                      authenticated != true)
            .accessibilityIdentifier("SCARLET_MANUAL_SIDESTORE_REFRESH")
            if let statusMessage {
                Text(statusMessage)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("SCARLET_REFRESH_STATUS")
            }
        } header: {
            Text("서명 갱신 · 권한")
        } footer: {
            Text("로그인, 서명 인증서, App Group 접근, 실제 재설치는 서로 다른 상태입니다. 자동 7일 갱신은 아직 연결되지 않았습니다.")
        }
        .onAppear(perform: inspect)
    }
}
