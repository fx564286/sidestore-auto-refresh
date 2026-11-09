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
    @State private var statusMessage: String?
    @State private var certificateRecoveryStatus: String?
    @State private var isSelectingP12 = false
    @State private var pendingP12: Data?
    @State private var isAskingP12Password = false
    @State private var p12Password = ""

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

    // Stage 1: recover an EXISTING SideStore certificate from the same-team,
    // entitled Keychain service. The host, not a duplicate login screen,
    // performs the established readback-validated bridge.
    private func recoverSideStoreCertificate() {
        inspect()
        if readiness.liveContainerCertificatePresent &&
            readiness.liveContainerPasswordPresent {
            certificateRecoveryStatus = "이미 LiveContainer 서명 인증서가 있습니다. 기존 인증서는 보존됩니다."
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

    // Stage 2: SideInstaller exposes its own Apple-authorized certificate
    // issuance/export UI. It does NOT publish an export-to-Scarlet deep link,
    // and iOS does not allow us to read its private key store. Launch its app
    // only when the user explicitly chooses the fallback.
    private func openSideInstaller() {
        guard let url = URL(string: "sideinstaller://") else { return }
        ScarletDiagnosticRecorder.shared.record(
            "certificate", "sideinstaller_fallback_requested")
        UIApplication.shared.open(url, options: [:]) { opened in
            Task { @MainActor in
                certificateRecoveryStatus = opened
                    ? "SideInstaller에서 인증서 → 발급 또는 현재 서명 인증서 → 내보내기 → 파일에 저장을 선택한 후 홍수정으로 돌아와 P12 가져오기를 누르세요."
                    : "SideInstaller를 실행할 수 없습니다. 설치 상태를 확인하세요. 이미 내보낸 P12는 파일 앱에서 직접 가져올 수 있습니다."
                ScarletDiagnosticRecorder.shared.record(
                    "certificate", opened ? "sideinstaller_opened" : "sideinstaller_unavailable",
                    status: opened ? "info" : "blocked")
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

    private func importExportedP12() {
        // Clear the temporary in-memory P12/password on all exits.
        defer { pendingP12 = nil; p12Password = "" }
        inspect()
        guard readiness.canRequestNativeRefresh else {
            certificateRecoveryStatus = "서명 팀 또는 App Group 권한이 올바르지 않습니다. 가져오지 않았습니다."
            return
        }
        guard LCUtils.certificateData() == nil else {
            certificateRecoveryStatus = "기존 인증서가 있습니다. 덮어쓰지 않았습니다."
            return
        }
        guard let archive = pendingP12, !archive.isEmpty else {
            certificateRecoveryStatus = "가져올 인증서가 없습니다."
            return
        }
        guard let actualTeam = LCSharedUtils.teamIdentifier(),
              let archiveTeam = LCUtils.getCertTeamId(
                  withKeyData: archive, password: p12Password),
              actualTeam == archiveTeam else {
            certificateRecoveryStatus = "P12 암호 오류 또는 현재 설치된 홍수정의 서명 팀과 불일치합니다."
            ScarletDiagnosticRecorder.shared.record(
                "certificate", "import_blocked", status: "blocked",
                fields: ["reason": "password_or_team_mismatch"])
            return
        }
        let password = p12Password
        LCUtils.appGroupUserDefault.set(archive, forKey: "LCCertificateData")
        LCUtils.appGroupUserDefault.set(password, forKey: "LCCertificatePassword")
        guard LCUtils.certificateData() == archive &&
              LCSharedUtils.certificatePassword() == password else {
            LCUtils.appGroupUserDefault.removeObject(forKey: "LCCertificateData")
            LCUtils.appGroupUserDefault.removeObject(forKey: "LCCertificatePassword")
            certificateRecoveryStatus = "인증서 저장 후 확인에 실패했습니다. 적용하지 않았습니다."
            ScarletDiagnosticRecorder.shared.record(
                "certificate", "import_readback_failed", status: "error")
            return
        }
        LCUtils.appGroupUserDefault.set(Date(), forKey: "LCCertificateUpdateDate")
        certificateRecoveryStatus = "같은 개발 팀의 P12 저장 및 읽기 검증 완료. JIT-Less 서명 진단으로 실제 서명 상태를 확인하세요."
        ScarletDiagnosticRecorder.shared.record(
            "certificate", "sideinstaller_export_imported", status: "success",
            fields: ["reason": "same_team_verified_readback"])
        inspect()
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
            if !readiness.liveContainerCertificatePresent ||
                !readiness.liveContainerPasswordPresent {
                Button(action: recoverSideStoreCertificate) {
                    Label("1. SideStore 인증서 자동 조회", systemImage: "arrow.triangle.2.circlepath")
                }
                .accessibilityIdentifier("SCARLET_P12_FROM_SIDESTORE")
                Button(action: openSideInstaller) {
                    Label("2. SideInstaller에서 발급·내보내기", systemImage: "checkmark.shield")
                }
                .accessibilityIdentifier("SCARLET_P12_SIDEINSTALLER_FALLBACK")
                Button {
                    isSelectingP12 = true
                } label: {
                    Label("3. 파일에서 P12 가져오기", systemImage: "doc.badge.plus")
                }
                .accessibilityIdentifier("SCARLET_P12_IMPORT_FROM_FILES")
            }
            if let certificateRecoveryStatus {
                Text(certificateRecoveryStatus)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .accessibilityIdentifier("SCARLET_P12_PIPELINE_RESULT")
            }
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
        .onReceive(NotificationCenter.default.publisher(
            for: Notification.Name("ScarletCertificateAutoBridgeFinished"))) { _ in
            inspect()
            let recovered = readiness.liveContainerCertificatePresent &&
                readiness.liveContainerPasswordPresent
            certificateRecoveryStatus = recovered
                ? "SideStore 인증서를 가져와 읽기 검증했습니다."
                : "SideStore Keychain에서 같은 팀의 P12를 찾지 못했습니다. SideInstaller 발급·내보내기로 진행하세요."
            ScarletDiagnosticRecorder.shared.record(
                "certificate",
                recovered ? "sidestore_imported" : "sidestore_missing",
                status: recovered ? "success" : "blocked")
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
            Button("가져오기") { importExportedP12() }
            Button("취소", role: .cancel) {
                pendingP12 = nil
                p12Password = ""
            }
        } message: {
            Text("SideInstaller에서 내보낸 P12만 선택하세요. 설치된 홍수정과 개발 팀이 동일해야 하며 기존 인증서를 덮어쓰지 않습니다.")
        }
    }
}
