// Scarlet Crystal signing readiness + explicit manual SideStore refresh UI.
// The profile/App Group entitlements are Apple-issued, never toggled or forged.
// A refresh IPC acknowledgement is NOT proof that a signed app was installed.
import Foundation
import Security
import SwiftUI
import SideStoreSupport
import UniformTypeIdentifiers

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
    @State private var lastRefreshAttemptState: String = "없음"
    @State private var lastRefreshFailureReason: String?
    @State private var refreshManagedAppCount: Int?
    @State private var refreshHostManaged: Bool?
    @State private var statusMessage: String?
    @State private var certificateRecoveryStatus: String?
    @State private var isSelectingP12 = false
    @State private var pendingP12: Data?
    // Safe enum only, never serial/key/password. Preserve through explicit
    // P12 replacement confirmation so success copy matches the real source.
    @State private var pendingCertificateOrigin = "unknown"
    @State private var isAskingP12Password = false
    @State private var p12Password = ""
    @State private var isConfirmingCertReplacement = false
    @State private var hadCertificateBeforeBridge = false
    @State private var isIssuingNativeCertificate = false
    @State private var isRetrievingSideStoreCertificate = false

    private var displayRefreshState: String {
        switch lastRefreshAttemptState {
        case "기록 없음": return "대기 중"
        case "요청 중 · 검증 전": return "갱신 확인 중"
        case "요청 반환 · 재설치 확인 안 됨",
             "갱신 기록 확인 · 설치 미확인",
             "상태 불명 · 이전 요청의 설치 완료 기록 없음":
            return "설치 확인 필요"
        case "차단 · SideStore 로그인 상태 확인 필요":
            return "로그인 필요"
        case "차단 · SideStore 갱신 사전검사 실패":
            return "갱신 준비 필요"
        case "실패 · SideStore 갱신 오류":
            return "갱신 실패"
        default: return lastRefreshAttemptState
        }
    }

    private func inspect() {
        readiness = ScarletSigningReadiness.inspect()
        let defaults = UserDefaults.standard
        let outcomeKey = "Scarlet.Refresh.LastAttemptOutcome"
        let prior = defaults.string(forKey: outcomeKey) ?? "기록 없음"
        if prior.hasPrefix("요청 중") {
            // V23 could leave a forever-pending state after returning early
            // without a completion write. Do not pretend a renewal succeeded.
            let start = defaults.object(forKey:
                "Scarlet.Refresh.LastAttemptStartedAt") as? Date
            if start == nil || Date().timeIntervalSince(start!) > 7 * 60 {
                defaults.set("상태 불명 · 이전 요청의 설치 완료 기록 없음",
                             forKey: outcomeKey)
                ScarletDiagnosticRecorder.shared.record(
                    "refresh", "orphaned_request_state_reconciled",
                    status: "warning", fields: ["reason": "no_terminal_receipt"])
            }
        }
        lastRefreshAttemptState = defaults.string(forKey: outcomeKey) ?? "기록 없음"
        lastRefreshFailureReason = UserDefaults.standard.string(
            forKey: "Scarlet.Refresh.LastFailureReason")
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
        UserDefaults.standard.set(Date(), forKey:
            "Scarlet.Refresh.LastAttemptStartedAt")
        UserDefaults.standard.set("요청 중 · 검증 전",
            forKey: "Scarlet.Refresh.LastAttemptOutcome")
        UserDefaults.standard.removeObject(forKey: "Scarlet.Refresh.LastFailureReason")
        lastRefreshFailureReason = nil
        statusMessage = "내장 SideStore에서 앱 새로고침을 요청하는 중입니다."
        Task { @MainActor in
            defer { refreshing = false }
            let verified = await ScarletConnectedSideSignEngine().storedAuthenticated()
            authenticated = verified
            guard verified else {
                statusMessage = "내장 SideStore 로그인 세션이 없습니다. 먼저 Apple ID 인증을 완료하세요."
                UserDefaults.standard.set("차단 · SideStore 로그인 상태 확인 필요",
                    forKey: "Scarlet.Refresh.LastAttemptOutcome")
                UserDefaults.standard.set("auth_unavailable",
                    forKey: "Scarlet.Refresh.LastFailureReason")
                lastRefreshAttemptState = "차단 · SideStore 로그인 상태 확인 필요"
                lastRefreshFailureReason = "auth_unavailable"
                ScarletDiagnosticRecorder.shared.record("refresh", "manual_blocked",
                    status: "blocked", fields: ["reason": "auth_unavailable"])
                return
            }
            // Critical native difference from SideInstaller: the embedded
            // SideStore refreshes only its CoreData-managed InstalledApps,
            // not every app installed on iOS via an external signer.
            let nativeState = await ScarletNativeRefreshInspector.inspect()
            refreshManagedAppCount = nativeState.count
            refreshHostManaged = nativeState.hostManaged
            ScarletDiagnosticRecorder.shared.record(
                "refresh", "sidestore_managed_apps_inspected",
                status: nativeState.canRefreshHost ? "success" : "blocked",
                fields: ["count": String(nativeState.count),
                         "host_managed": nativeState.hostManaged ? "true" : "false",
                         "signing_ready": nativeState.signingReady ? "true" : "false",
                         "reason": nativeState.reason])
            guard nativeState.canRefreshHost else {
                let message = ScarletRefreshFailureDiagnosis.nativeGuidance(nativeState.reason)
                statusMessage = message
                lastRefreshAttemptState = "차단 · SideStore 갱신 사전검사 실패"
                lastRefreshFailureReason = nativeState.reason
                UserDefaults.standard.set(lastRefreshAttemptState,
                    forKey: "Scarlet.Refresh.LastAttemptOutcome")
                UserDefaults.standard.set(nativeState.reason,
                    forKey: "Scarlet.Refresh.LastFailureReason")
                return
            }
            ScarletInstalledProfileReadback.beginRequest(source: "manual")
            do {
                // Native upstream action; do not navigate to the guest SideStore.
                // It can refresh registered apps, but must not be taken as proof
                // this Scarlet host was re-signed and reinstalled.
                let receipt = try await ScarletNativeRefreshExecutor.execute()
                ScarletDiagnosticRecorder.shared.record(
                    "refresh", "native_worker_operation_returned",
                    status: "info",
                    fields: ["reason": receipt, "installation_verified": "false"])
                let nativeRecordChanged = receipt ==
                    "native_profile_date_advanced_install_unverified" ||
                    receipt == "native_refresh_record_updated_install_unverified"
                statusMessage = nativeRecordChanged
                    ? "갱신 기록이 업데이트됐습니다. 실제 설치 반영은 확인 중입니다."
                    : "갱신 작업은 끝났지만, 실제 설치 완료는 확인되지 않았습니다."
                UserDefaults.standard.set(nativeRecordChanged
                    ? "갱신 기록 확인 · 설치 미확인"
                    : "요청 반환 · 재설치 확인 안 됨",
                    forKey: "Scarlet.Refresh.LastAttemptOutcome")
                UserDefaults.standard.removeObject(forKey: "Scarlet.Refresh.LastFailureReason")
                lastRefreshAttemptState = nativeRecordChanged
                    ? "갱신 기록 확인 · 설치 미확인"
                    : "요청 반환 · 재설치 확인 안 됨"
                lastRefreshFailureReason = nil
                ScarletDiagnosticRecorder.shared.record("refresh", "manual_request_returned",
                    status: "info", fields: ["installation_verified": "false"])
                inspect()
            } catch {
                ScarletInstalledProfileReadback.discardFailedRequest()
                let failure = (error as? ScarletNativeRefreshFailure)?.reason ??
                    ScarletRefreshFailureDiagnosis.category(error)
                statusMessage = error is ScarletNativeRefreshFailure
                    ? ScarletRefreshFailureDiagnosis.nativeGuidance(failure)
                    : ScarletRefreshFailureDiagnosis.guidance(failure)
                UserDefaults.standard.set("실패 · SideStore 갱신 오류",
                    forKey: "Scarlet.Refresh.LastAttemptOutcome")
                UserDefaults.standard.set(failure,
                    forKey: "Scarlet.Refresh.LastFailureReason")
                lastRefreshFailureReason = failure
                lastRefreshAttemptState = "실패 · SideStore 갱신 오류"
                // The P12 may be healthy. A SideStore runtime crash or
                // extension launch failure is NOT a certificate-expiry
                // diagnosis and must not trigger certificate replacement.
                certificateRecoveryStatus = nil
                ScarletDiagnosticRecorder.shared.record("refresh", "manual_request_failed",
                    status: "error", fields: ["reason": failure])
                ScarletDiagnosticRecorder.shared.recordError(
                    "refresh", "manual_request_underlying_error", error: error)
            }
        }
    }

    // Stage 1: recover an EXISTING SideStore certificate from the same-team,
    // entitled Keychain service. The host, not a duplicate login screen,
    // performs the established readback-validated bridge.
    private func recoverSideStoreCertificate() {
        inspect()
        hadCertificateBeforeBridge = readiness.liveContainerCertificatePresent &&
            readiness.liveContainerPasswordPresent
        if hadCertificateBeforeBridge {
            // Host cannot read SideStore's private Keychain after a valid
            // certificate has already been placed in LC storage. Keep it
            // intact, and provide the explicit provider fallback instead
            // of falsely declaring a renewed certificate.
            certificateRecoveryStatus = "기존 P12는 유지됩니다. 새 인증서가 필요하면 바로 아래 '인증서 받기'를 선택하세요."
            ScarletDiagnosticRecorder.shared.record(
                "certificate", "existing_cert_reissue_unverified",
                fields: ["reason": "provider_isolated"])
            return
        }
        guard readiness.canRequestNativeRefresh else {
            certificateRecoveryStatus = "Apple 서명·App Group 권한이 맞지 않아 인증서 복구를 중단했습니다."
            ScarletDiagnosticRecorder.shared.record(
                "certificate", "provider_blocked", status: "blocked",
                fields: ["reason": readiness.safeBlockCategory])
            return
        }
        certificateRecoveryStatus = "SideStore에 이미 보관된 인증서를 확인하고 있습니다."
        ScarletDiagnosticRecorder.shared.record(
            "certificate", "sidestore_provider_requested")
        NotificationCenter.default.post(
            name: Notification.Name("ScarletCertificateAutoBridgeRequested"),
            object: nil)
    }

    // Apple-approved portal issuance via the existing authenticated
    // SideStore LiveProcess. No external SideInstaller app or credential
    // transfer URL. The P12 comes back only on the existing XPC endpoint;
    // this host validates team and obtains explicit replacement consent.
    private func requestNativeCertificate() {
        guard !isIssuingNativeCertificate && !isRetrievingSideStoreCertificate else { return }
        inspect()
        guard readiness.canRequestNativeRefresh else {
            certificateRecoveryStatus = "서명 팀 또는 앱 그룹 권한을 확인할 수 없습니다."
            return
        }
        isIssuingNativeCertificate = true
        certificateRecoveryStatus = "SideStore 인증서를 앱 내부에서 확인·발급하는 중입니다."
        ScarletDiagnosticRecorder.shared.record(
            "certificate", "native_provider_started")
        Task { @MainActor in
            defer { isIssuingNativeCertificate = false }
            do {
                let (archive, password) =
                    try await ScarletNativeCertificateTransport.shared.obtain()
                let source = ScarletNativeCertificateTransport.shared.lastResolution
                ScarletDiagnosticRecorder.shared.record(
                    "certificate", "provider_origin_checked",
                    fields: ["source": source])
                pendingP12 = archive
                pendingCertificateOrigin = source
                p12Password = password
                importExportedP12()
                ScarletDiagnosticRecorder.shared.record(
                    "certificate", "native_provider_returned",
                    fields: ["result": "team_validation_pending_or_passed"])
                // R6P21: LC P12 equality does NOT prove SideStore's signing
                // Keychain is populated. R6P20 read it BEFORE this provider,
                // then never again. Re-read the real SideStore worker NOW.
                // This is observation only: no certificate import/reissue,
                // keychain deletion, profile updates or auto-install claim.
                let nativeState = await ScarletNativeRefreshInspector.inspect()
                refreshManagedAppCount = nativeState.count
                refreshHostManaged = nativeState.hostManaged
                ScarletDiagnosticRecorder.shared.record(
                    "certificate", "sidestore_signing_rechecked",
                    status: nativeState.signingReady ? "success" : "warning",
                    fields: ["count": String(nativeState.count),
                             "host_managed": nativeState.hostManaged ? "true" : "false",
                             "signing_ready": nativeState.signingReady ? "true" : "false",
                             "reason": nativeState.reason])
                if !nativeState.signingReady {
                    certificateRecoveryStatus = "기존 LC 인증서는 유지됩니다. SideStore 내부 서명 인증서 준비는 아직 확인되지 않았습니다."
                }
            } catch {
                let failure = error as NSError
                certificateRecoveryStatus =
                    "SideStore 발급 요청 실패. 기존 SideStore 인증서를 자동 확인합니다."
                ScarletDiagnosticRecorder.shared.record(
                    "certificate", "native_provider_failed",
                    status: "error",
                    fields: ["domain": "scarlet.certificate.worker",
                             "code": String(failure.code)])
                // SideInstaller-style retrieval is an internal fallback, not
                // a second user-facing certificate import button.
                retrieveSideInstallerStyleCertificate()
            }
        }
    }

    // SideInstaller's original "Use SideStore certificate" action requests
    // SideStore's EXISTING signing archive rather than issuing a new cert.
    // In LiveContainer, SideInstaller falls back to the locally held P12.
    // Perform both operations inside this app; the existing XPC connection
    // carries the archive, and this host verifies its Team ID before saving.
    private func retrieveSideInstallerStyleCertificate() {
        guard !isRetrievingSideStoreCertificate else { return }
        isRetrievingSideStoreCertificate = true
        certificateRecoveryStatus = "SideStore가 보유한 인증서를 확인하는 중입니다."
        ScarletDiagnosticRecorder.shared.record(
            "certificate", "sideinstaller_style_retrieval_started")
        Task { @MainActor in
            defer { isRetrievingSideStoreCertificate = false }
            do {
                let (archive, password) =
                    try await ScarletNativeCertificateTransport.shared
                        .retrieveSideStoreCertificate()
                pendingP12 = archive
                pendingCertificateOrigin = "existing_stored"
                p12Password = password
                importExportedP12()
                ScarletDiagnosticRecorder.shared.record(
                    "certificate", "sideinstaller_style_retrieval_finished",
                    fields: ["result": "host_team_check_applied"])
            } catch {
                // SideInstaller in LiveContainer reads LC's already-held
                // certificate when SideStore cannot provide a callback.
                // This fallback confirms presence, not newly issued cert.
                inspect()
                if let localCert = LCUtils.certificateData(),
                   let password = LCSharedUtils.certificatePassword(),
                   let hostTeam = LCSharedUtils.teamIdentifier(),
                   LCUtils.getCertTeamId(withKeyData: localCert,
                                         password: password) == hostTeam {
                    certificateRecoveryStatus =
                        "기존 인증서는 현재 앱에 보관돼 있습니다. 새 발급·갱신은 확인되지 않았습니다."
                    ScarletDiagnosticRecorder.shared.record(
                        "certificate", "sideinstaller_style_local_fallback",
                        fields: ["result": "existing_same_team_archive"])
                } else {
                    certificateRecoveryStatus =
                        "SideStore 기존 인증서를 찾지 못했습니다. 추가 인증서 관리에서 P12 파일을 선택할 수 있습니다."
                    ScarletDiagnosticRecorder.shared.record(
                        "certificate", "sideinstaller_style_retrieval_missing",
                        status: "blocked", fields: ["reason": "missing_signable_archive"])
                }
            }
        }
    }

    // Stage 3: Explicit Files picker; never read another app's sandbox,
    // transmit the signing key, write an unverified archive, or revoke certs.
    private func stageExportedP12(_ result: Result<URL, Error>) {
        switch result {
        case .failure:
            certificateRecoveryStatus = "P12 파일을 선택하지 않았습니다."
        case .success(let url):
            guard ["p12", "pfx"].contains(url.pathExtension.lowercased()) else {
                certificateRecoveryStatus = "확장자가 .p12 또는 .pfx인 인증서를 선택하세요."
                return
            }
            let accessed = url.startAccessingSecurityScopedResource()
            defer { if accessed { url.stopAccessingSecurityScopedResource() } }
            do {
                let metadata = try FileManager.default.attributesOfItem(atPath: url.path)
                guard let bytes = metadata[.size] as? NSNumber,
                      bytes.int64Value > 0 && bytes.int64Value < 10_000_000 else {
                    certificateRecoveryStatus = "P12 파일 크기가 올바르지 않습니다(최대 10MB)."
                    return
                }
                let data = try Data(contentsOf: url)
                guard data.count == bytes.intValue else {
                    certificateRecoveryStatus = "인증서 파일의 읽기 크기가 일치하지 않습니다."
                    return
                }
                pendingP12 = data
                pendingCertificateOrigin = "external_file"
                p12Password = ""
                isAskingP12Password = true
                ScarletDiagnosticRecorder.shared.record(
                    "certificate", "sideinstaller_export_selected")
            } catch {
                certificateRecoveryStatus = "파일 앱에서 P12를 읽지 못했습니다. 접근 권한을 확인하세요."
                ScarletDiagnosticRecorder.shared.record(
                    "certificate", "file_read_failed", status: "error")
            }
        }
    }

    private func clearStagedCertificate() {
        pendingP12 = nil
        p12Password = ""
        pendingCertificateOrigin = "unknown"
    }

    private func importExportedP12(replaceExisting: Bool = false) {
        inspect()
        guard readiness.canRequestNativeRefresh else {
            certificateRecoveryStatus = "App Group 또는 서명 팀 권한 불일치로 적용하지 않았습니다."
            clearStagedCertificate()
            return
        }
        guard let archive = pendingP12, !archive.isEmpty else {
            certificateRecoveryStatus = "선택한 P12가 없습니다."
            clearStagedCertificate()
            return
        }
        guard let hostTeam = LCSharedUtils.teamIdentifier(),
              let archiveTeam = LCUtils.getCertTeamId(
                  withKeyData: archive, password: p12Password),
              hostTeam == archiveTeam else {
            certificateRecoveryStatus = "P12 암호 오류 또는 현재 개발 팀과 불일치합니다."
            ScarletDiagnosticRecorder.shared.record(
                "certificate", "import_blocked", status: "blocked",
                fields: ["reason": "password_or_team_mismatch"])
            clearStagedCertificate()
            return
        }
        let existingCert = LCUtils.certificateData()
        let existingPassword = LCSharedUtils.certificatePassword()
        if existingCert == archive && existingPassword == p12Password {
            certificateRecoveryStatus = "기존 P12와 동일합니다. 신규 발급·갱신은 발생하지 않았습니다."
            ScarletDiagnosticRecorder.shared.record(
                "certificate", "native_provider_same_certificate",
                fields: ["reason": "unchanged"])
            clearStagedCertificate()
            return
        }
        let existingDate = LCUtils.appGroupUserDefault.object(
            forKey: "LCCertificateUpdateDate")
        if existingCert != nil && !replaceExisting {
            certificateRecoveryStatus = "새 P12의 팀 일치 검증을 통과했습니다. 기존 인증서를 교체하려면 확인이 필요합니다."
            isConfirmingCertReplacement = true
            return
        }

        let password = p12Password
        let defaults = LCUtils.appGroupUserDefault
        defaults.set(archive, forKey: "LCCertificateData")
        defaults.set(password, forKey: "LCCertificatePassword")
        let stored = LCUtils.certificateData() == archive &&
            LCSharedUtils.certificatePassword() == password
        if !stored {
            // Restore the previously working signing material on any error.
            if let existingCert { defaults.set(existingCert, forKey: "LCCertificateData") }
            else { defaults.removeObject(forKey: "LCCertificateData") }
            if let existingPassword {
                defaults.set(existingPassword, forKey: "LCCertificatePassword")
            } else { defaults.removeObject(forKey: "LCCertificatePassword") }
            if let existingDate { defaults.set(existingDate, forKey: "LCCertificateUpdateDate") }
            else { defaults.removeObject(forKey: "LCCertificateUpdateDate") }
            certificateRecoveryStatus = "새 P12 저장·읽기 검증 실패. 이전 인증서를 복원했습니다."
            ScarletDiagnosticRecorder.shared.record(
                "certificate", "replacement_readback_failed", status: "error")
            clearStagedCertificate()
            return
        }
        defaults.set(Date(), forKey: "LCCertificateUpdateDate")
        switch pendingCertificateOrigin {
        case "new_apple_portal":
            certificateRecoveryStatus = "Apple 포털 신규 발급 확인 · P12 팀 일치 및 저장 검증 완료. 실제 앱 재설치는 별도 확인이 필요합니다."
        case "existing_active", "existing_portal", "existing_stored":
            certificateRecoveryStatus = "SideStore 기존 인증서 가져오기·저장 완료. Apple에서 새 인증서가 발급된 것은 아닙니다."
        case "external_file":
            certificateRecoveryStatus = "선택한 P12 저장 검증 완료. Apple 신규 발급 여부는 파일만으로 확인할 수 없습니다."
        default:
            certificateRecoveryStatus = "P12 팀 일치 및 저장 검증 완료. 신규 발급 여부는 확인되지 않았습니다."
        }
        ScarletDiagnosticRecorder.shared.record(
            "certificate", "p12_origin_at_storage",
            fields: ["source": pendingCertificateOrigin])
        ScarletDiagnosticRecorder.shared.record(
            "certificate", "p12_stored_verified",
            status: "success",
            fields: ["reason": existingCert == nil ? "new_same_team_readback"
                                                 : "explicit_replacement_same_team"])
        clearStagedCertificate()
        inspect()
    }

    var body: some View {
        Section {
            LabeledContent("자동 갱신",
                value: lastRefreshAttemptState == "기록 없음" ?
                       "대기 중" : displayRefreshState)
            if let refreshManagedAppCount {
                LabeledContent("자동 갱신 대상", value: String(refreshManagedAppCount))
                    .accessibilityIdentifier("SCARLET_MANAGED_REFRESH_APP_COUNT")
            }
            if let refreshHostManaged {
                LabeledContent("이 앱 자동 갱신",
                               value: refreshHostManaged ? "등록됨" : "등록 안 됨")
                    .accessibilityIdentifier("SCARLET_MANAGED_HOST_REGISTRATION")
            }
            if let lastRefreshFailureReason {
                LabeledContent("갱신 문제", value: "확인 필요")
                Text(ScarletRefreshFailureDiagnosis.nativeGuidance(lastRefreshFailureReason))
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("SCARLET_REFRESH_FAILURE_CATEGORY")
            }
            // V29: SideInstaller-style pairing is owned by Scarlet's
            // native UI; the embedded SideStore keeps only its engine
            // and its existing Keychain, database and pairing storage.
            if #available(iOS 27.0, *) {
                ScarletPairingStatusRow()
                Button {
                    ScarletDiagnosticRecorder.shared.record(
                        "pairing", "sheet_requested")
                    NotificationCenter.default.post(
                        name: Notification.Name("ScarletPresentDevicePairing"),
                        object: nil)
                } label: {
                    Label("페어링 설정", systemImage: "iphone.radiowaves.left.and.right")
                }
                .accessibilityIdentifier("SCARLET_NATIVE_DEVICE_PAIRING")
            }
            // The native refresh action existed since V12 but had NO
            // rendered button in Scarlet's own settings. SideStore could
            // refresh interactively; Scarlet's users could only watch a
            // potentially stale background status. Restore actual control
            // without navigating to the embedded SideStore guest screen.
            Button(action: requestManualRefresh) {
                if refreshing {
                    HStack(spacing: 9) {
                        ProgressView()
                        Text("앱 갱신 중")
                    }
                } else {
                    Label("지금 갱신", systemImage: "arrow.triangle.2.circlepath")
                }
            }
            .disabled(refreshing || !readiness.canRequestNativeRefresh)
            .accessibilityIdentifier("SCARLET_NATIVE_REFRESH_NOW")
            LabeledContent("서명 상태",
                value: readiness.canRequestNativeRefresh &&
                       readiness.liveContainerCertificatePresent &&
                       readiness.liveContainerPasswordPresent ? "준비됨" : "확인 필요")
            Button(action: requestNativeCertificate) {
                if isIssuingNativeCertificate || isRetrievingSideStoreCertificate {
                    HStack(spacing: 9) {
                        ProgressView()
                        Text("인증서 확인 중")
                    }
                } else {
                    Label("SideStore 인증서 받기", systemImage: "checkmark.shield")
                }
            }
            .disabled(isIssuingNativeCertificate ||
                      isRetrievingSideStoreCertificate ||
                      !readiness.canRequestNativeRefresh)
            .accessibilityIdentifier("SCARLET_P12_NATIVE_ISSUE")
            Button { isSelectingP12 = true } label: {
                Label("P12 파일 선택", systemImage: "doc.badge.plus")
            }
            .accessibilityIdentifier("SCARLET_P12_IMPORT_FROM_FILES")
            if let certificateRecoveryStatus {
                Text(certificateRecoveryStatus)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("SCARLET_P12_PIPELINE_RESULT")
            }
            if let statusMessage {
                Text(statusMessage)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("SCARLET_REFRESH_STATUS")
            }
        } header: {
            Text("서명 및 페어링")
        }
        .onAppear(perform: inspect)
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletRefreshOutcomeChanged"))) { _ in
            inspect()
        }
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletCertificateAutoBridgeFinished"))) { _ in
            inspect()
            let newlyRecovered = !hadCertificateBeforeBridge &&
                readiness.liveContainerCertificatePresent &&
                readiness.liveContainerPasswordPresent
            certificateRecoveryStatus = newlyRecovered
                ? "SideStore의 기존 P12를 가져와 읽기 검증했습니다."
                : "SideStore Keychain에서 새 P12를 확인하지 못했습니다. 바로 아래 인증서 받기를 사용하세요."
            ScarletDiagnosticRecorder.shared.record(
                "certificate",
                newlyRecovered ? "sidestore_imported" : "sidestore_reissue_unverified",
                status: newlyRecovered ? "success" : "blocked")
        }
        .fileImporter(isPresented: $isSelectingP12,
                      allowedContentTypes: [
                        UTType(filenameExtension: "p12") ?? .data,
                        UTType(filenameExtension: "pfx") ?? .data
                      ]) { result in
            stageExportedP12(result)
        }
        .alert("P12 인증서 암호", isPresented: $isAskingP12Password) {
            SecureField("암호가 없으면 비워 두세요", text: $p12Password)
            Button("검증 후 가져오기") { importExportedP12() }
            Button("취소", role: .cancel) {
                clearStagedCertificate()
            }
        } message: {
            Text("기기 파일에 저장된 P12/PFX를 선택하면 팀 ID를 검사합니다. 기존 서명 인증서 교체에는 별도 확인이 필요합니다.")
        }
        .confirmationDialog(
            "기존 서명 인증서를 교체하시겠습니까?",
            isPresented: $isConfirmingCertReplacement,
            titleVisibility: .visible) {
                Button("팀 일치 검증된 P12로 교체") {
                    importExportedP12(replaceExisting: true)
                }
                Button("기존 인증서 유지", role: .cancel) {
                    clearStagedCertificate()
                }
            } message: {
                Text("교체 후에도 SideStore 로그인·서명·설치 프로파일의 갱신은 별도 검증이 필요합니다. 실패 시 기존 인증서를 복원합니다.")
            }
    }
}
