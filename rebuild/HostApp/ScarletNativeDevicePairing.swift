// Scarlet Crystal V29: genuine iOS 27 remote pairing in Scarlet's own UI.
// Rust pairing transport: pinned StikPair by StephenDev0 (MIT Non-Commercial).
// No new Apple App IDs, SideInstaller launch, notch or Dynamic Island widget.
// The PIN may appear as a normal iOS notification while Settings is open.
// The pairing file never enters the diagnostic journal or remote services.
import SwiftUI
import BackgroundTasks
import UserNotifications
import Foundation
import SideStoreSupport

@available(iOS 27.0, *)
@MainActor
final class ScarletDevicePairingModel: NSObject, ObservableObject, @preconcurrency NetServiceDelegate {
    static let shared = ScarletDevicePairingModel()
    static let taskIdentifier = "com.kdt.livecontainer.P8EZT3U5N4.pairing"

    @Published private(set) var phase = "확인 중"
    @Published private(set) var pin: String?
    @Published private(set) var active = false
    @Published private(set) var verified = false
    @Published private(set) var failureReason: String?
    private var service: NetService?
    private var backgroundTask: BGContinuedProcessingTask?
    private var waitingForHost = false
    private var taskFinished = false
    private var currentServicePort: UInt16 = 0
    @Published private(set) var savedRecordState = "확인 중"
    private var stateReadGeneration: UInt64 = 0
    private var lastReportedPairingState: String?
    private var stateReadInFlight = false

    // Display only actionable Korean in the UI. Raw diagnostics retain
    // the safe error category without exposing internal engine identifiers.
    func errorDescription(for reason: String) -> String {
        switch reason {
        case "background_expired", "pairing_validation_unresponsive",
             "pairing_state_read_timeout":
            return "연결 시간이 초과됐습니다. 다시 시도해 주세요."
        case "bonjour_publish_failed":
            return "로컬 네트워크 권한을 확인해 주세요."
        case "vpn_unavailable", "device_endpoint_unavailable",
             "device_network_unavailable", "transport_unavailable":
            return "기기 연결을 확인할 수 없습니다."
        case "pairing_invalid", "pairing_protocol_mismatch",
             "pairing_file_invalid", "empty_pairing_file":
            return "페어링 정보가 올바르지 않습니다. 다시 시도해 주세요."
        default:
            return "페어링을 완료하지 못했습니다. 다시 시도해 주세요."
        }
    }

    func refreshStoredState() {
        guard !active && !stateReadInFlight else { return }
        stateReadInFlight = true
        stateReadGeneration &+= 1
        let generation = stateReadGeneration
        Task { @MainActor in
            defer { stateReadInFlight = false }
            let (ready, reason) = await ScarletNativePairingInstaller.inspectPersistedState()
            guard !active && generation == stateReadGeneration else { return }
            savedRecordState = ready ? "페어링 됨" :
                reason == "pairing_file_missing" ? "페어링 필요" : "연결 확인 필요"
            verified = ready
            if ready {
                failureReason = nil
                phase = "페어링 됨"
            } else if reason == "pairing_file_missing" {
                phase = "페어링 필요"
            } else {
                phase = "연결 확인 필요"
            }
            // One categorical event per transition; never serialize UDID,
            // record, PIN, filesystem location or account identity.
            if lastReportedPairingState != reason {
                ScarletDiagnosticRecorder.shared.record(
                    "pairing", ready ? "pairing_restored" : "pairing_state_unverified",
                    status: ready ? "success" : "warning",
                    fields: ["reason": reason])
                lastReportedPairingState = reason
            }
        }
    }

    func registerAtLaunch() {
        BGTaskScheduler.shared.register(
            forTaskWithIdentifier: Self.taskIdentifier, using: .main
        ) { task in
            guard let task = task as? BGContinuedProcessingTask else { return }
            MainActor.assumeIsolated {
                self.runPairing(task: task)
            }
        }
    }

    private func candidateURL() -> URL {
        let directory = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true)
        return directory.appendingPathComponent("ScarletPendingRPPairingV29.plist")
    }

    func begin() {
        guard !active else { return }
        stateReadGeneration &+= 1 // stale readbacks cannot undo a new pairing
        active = true
        verified = false
        failureReason = nil
        pin = nil
        savedRecordState = "페어링 중"
        phase = "페어링 준비 중"
        ScarletDiagnosticRecorder.shared.record(
            "pairing", "pairing_started", fields: ["method": "on_device_rppairing"])
        Task {
            _ = try? await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound])
            guard active else { return }
            phase = "iPhone 설정에서 페어링을 완료해 주세요"
            let req = BGContinuedProcessingTaskRequest(
                identifier: Self.taskIdentifier,
                title: "Scarlet Crystal 기기 페어링",
                subtitle: "설정에서 Scarlet Crystal을 선택하세요")
            req.strategy = .queue
            do {
                try BGTaskScheduler.shared.submit(req)
                DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                    if !self.waitingForHost && self.active {
                        self.runPairing(task: nil)
                    }
                }
            } catch {
                // Some sideload signatures do not have background execution.
                // Attempt pairing in the foreground; never claim BG support.
                ScarletDiagnosticRecorder.shared.record(
                    "pairing", "background_task_unavailable",
                    status: "warning")
                runPairing(task: nil)
            }
        }
    }

    private func runPairing(task: BGContinuedProcessingTask?) {
        guard active else {
            task?.setTaskCompleted(success: false)
            return
        }
        // The 3s foreground fallback can start the Rust host before iOS
        // delivers its BGContinuedProcessingTask. Adopt that later task
        // instead of rejecting it, so pairing survives visiting Settings.
        if waitingForHost {
            if let task {
                backgroundTask = task
                task.progress.totalUnitCount = 100
                task.progress.completedUnitCount = pin == nil ? 5 : 50
                task.expirationHandler = {
                    Task { @MainActor in
                        self.phase = "연결이 끊겼습니다. 다시 시도해 주세요"
                        self.failureReason = "background_expired"
                        self.finishBackground(success: false)
                    }
                }
            }
            return
        }
        waitingForHost = true
        backgroundTask = task
        taskFinished = false
        task?.progress.totalUnitCount = 100
        task?.progress.completedUnitCount = 5
        task?.expirationHandler = {
            Task { @MainActor in
                self.phase = "연결이 끊겼습니다. 다시 시도해 주세요"
                self.failureReason = "background_expired"
                self.finishBackground(success: false)
            }
        }

        let filename = candidateURL().path
        let name = "Scarlet Crystal"
        let context = UInt(bitPattern: Unmanaged.passRetained(self).toOpaque())
        // The open-source StikPair host must run off the UIKit main thread.
        DispatchQueue.global(qos: .userInitiated).async(execute: DispatchWorkItem {
            let pointer = UnsafeMutableRawPointer(bitPattern: context)
            var result = StikPairResult()
            let code = "0.0.0.0".withCString { bind in
                name.withCString { host in
                    "Mac17,7".withCString { model in
                        filename.withCString { destination in
                            stikpair_run_host(
                                bind, 0, host, model, destination,
                                scarletPairingReady, scarletPairingPIN,
                                pointer, &result)
                        }
                    }
                }
            }
            // Keep sensitive pointer results local. Never log the UDID,
            // record contents, pairing identity or filesystem path.
            let resultPath = result.pairing_file_path.map { String(cString: $0) }
            let nonSensitiveFailure = code == 0
                ? nil : "native_pairing_failed_\(code)"
            stikpair_result_free(&result)
            if let pointer {
                Unmanaged<ScarletDevicePairingModel>.fromOpaque(pointer).release()
            }
            Task { @MainActor in
                self.stopAdvertising()
                self.waitingForHost = false
                if let resultPath, code == 0,
                   let bytes = try? Data(contentsOf: URL(fileURLWithPath: resultPath)),
                   bytes.count > 128, bytes.count <= 1024 * 1024 {
                    self.phase = "연결 확인 중"
                    self.backgroundTask?.progress.completedUnitCount = 70
                    let (ok, reason) = await ScarletNativePairingInstaller.install(
                        candidate: bytes)
                    self.verified = ok
                    self.savedRecordState = ok ? "페어링 됨" : "연결 확인 필요"
                    self.failureReason = ok ? nil : reason
                    self.phase = ok ? "페어링 됨" : "연결 확인 필요"
                    ScarletDiagnosticRecorder.shared.record(
                        "pairing", ok ? "pairing_verified" : "pairing_commit_failed",
                        status: ok ? "success" : "error",
                        fields: ["reason": reason])
                    try? FileManager.default.removeItem(
                        at: URL(fileURLWithPath: resultPath))
                    self.active = false
                    self.finishBackground(success: ok)
                } else {
                    self.active = false
                    self.verified = false
                    self.savedRecordState = "연결 확인 필요"
                    self.failureReason = nonSensitiveFailure ?? "empty_pairing_file"
                    self.phase = "페어링 실패"
                    ScarletDiagnosticRecorder.shared.record(
                        "pairing", "native_pairing_failed", status: "error",
                        fields: ["reason": self.failureReason ?? "unknown"])
                    self.finishBackground(success: false)
                }
            }
        })
    }

    private func finishBackground(success: Bool) {
        guard !taskFinished else { return }
        taskFinished = true
        backgroundTask?.progress.completedUnitCount = success ? 100 : 0
        backgroundTask?.setTaskCompleted(success: success)
        backgroundTask = nil
    }

    private func stopAdvertising() {
        service?.stop()
        service = nil
        currentServicePort = 0
    }

    fileprivate func advertise(_ name: String, port: UInt16,
        records: [String: Data]) {
        guard active else { return }
        stopAdvertising()
        currentServicePort = port
        let publisher = NetService(domain: "",
            type: "_remotepairing-pairable-host._tcp.",
            name: name, port: Int32(port))
        publisher.setTXTRecord(NetService.data(fromTXTRecord: records))
        publisher.delegate = self
        service = publisher
        publisher.publish()
        phase = "iPhone 설정에서 Scarlet Crystal을 선택해 주세요"
        ScarletDiagnosticRecorder.shared.record(
            "pairing", "bonjour_host_advertising")
    }

    fileprivate func showPIN(_ value: String) {
        guard active else { return }
        pin = value
        phase = "PIN을 입력해 주세요"
        backgroundTask?.progress.completedUnitCount = 50
        backgroundTask?.updateTitle(
            "Scarlet Crystal 기기 페어링", subtitle: "설정의 PIN 요청을 확인하세요")
        let message = UNMutableNotificationContent()
        message.title = "Scarlet Crystal 페어링 코드"
        message.body = "설정에 표시된 페어링 화면에 \(value)를 입력하세요."
        message.sound = .default
        UNUserNotificationCenter.current().add(
            UNNotificationRequest(identifier: "scarlet.pairing.pin",
                                  content: message, trigger: nil))
        // The PIN is intentionally omitted from exported logs.
        ScarletDiagnosticRecorder.shared.record(
            "pairing", "pin_available")
    }

    func netService(_ sender: NetService,
        didNotPublish errorDict: [String : NSNumber]) {
        phase = "로컬 네트워크 권한을 확인해 주세요"
        failureReason = "bonjour_publish_failed"
        ScarletDiagnosticRecorder.shared.record(
            "pairing", "bonjour_publish_failed", status: "error")
    }
}

// Native FFI callbacks never capture Swift state across Rust threads.
// Return to MainActor before publishing any UI or notification state.
@available(iOS 27.0, *)
private let scarletPairingReady: StikPairReadyCb = {
    context, serviceID, port, keys, values, count in
    guard let context, let serviceID else { return }
    let name = String(cString: serviceID)
    var entries: [String: Data] = [:]
    if let keys, let values {
        for i in 0..<Int(count) {
            if let k = keys[i], let v = values[i] {
                entries[String(cString: k)] =
                    Data(String(cString: v).utf8)
            }
        }
    }
    let model = Unmanaged<ScarletDevicePairingModel>.fromOpaque(
        context).takeUnretainedValue()
    Task { @MainActor in model.advertise(name, port: port, records: entries) }
}

@available(iOS 27.0, *)
private let scarletPairingPIN: StikPairPinCb = { code, context in
    guard let code, let context else { return }
    let pin = String(cString: code)
    let model = Unmanaged<ScarletDevicePairingModel>.fromOpaque(
        context).takeUnretainedValue()
    Task { @MainActor in model.showPIN(pin) }
}

@available(iOS 27.0, *)
struct ScarletPairingStatusRow: View {
    @ObservedObject private var pairing = ScarletDevicePairingModel.shared
    var body: some View {
        LabeledContent("페어링 상태", value: pairing.savedRecordState)
            .accessibilityIdentifier("SCARLET_PERSISTED_PAIRING_STATUS")
            .onAppear { pairing.refreshStoredState() }
    }
}

@available(iOS 27.0, *)
struct ScarletDevicePairingSheet: View {
    @ObservedObject private var pairing = ScarletDevicePairingModel.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("연결") {
                    LabeledContent("상태", value: pairing.savedRecordState)
                        .accessibilityIdentifier("SCARLET_PAIRING_SHEET_SAVED_STATE")
                    if pairing.active || pairing.phase != pairing.savedRecordState {
                        Label(pairing.phase, systemImage:
                            pairing.verified ? "checkmark.seal.fill"
                            : pairing.active ? "waveform.path"
                            : "antenna.radiowaves.left.and.right")
                    }
                    if pairing.active {
                        ProgressView()
                        Text("설정 → 개인정보 보호 및 보안 → 개발자 모드에서 Scarlet Crystal을 선택하세요.")
                            .font(.footnote)
                        Text("페어링 PIN은 알림으로 보내드립니다.")
                            .font(.footnote)
                    }
                    if let pin = pairing.pin {
                        LabeledContent("PIN 번호", value: pin)
                    }
                    if let reason = pairing.failureReason {
                        LabeledContent("문제", value: pairing.errorDescription(for: reason))
                    }
                    Button {
                        pairing.begin()
                    } label: {
                        Label(pairing.active ? "페어링 중" :
                              pairing.verified ? "다시 페어링" : "페어링 시작",
                              systemImage: "iphone.gen3.radiowaves.left.and.right")
                    }
                    .disabled(pairing.active)
                    .accessibilityIdentifier("SCARLET_NATIVE_RPPAIR_START")
                }
                Section {
                    Text("연결에 실패해도 기존 페어링 정보, 인증서와 설치된 앱은 그대로 유지됩니다.")
                        .font(.footnote)
                }
            }
            .navigationTitle("페어링")
            .scrollContentBackground(.hidden)
            .background(
                LinearGradient(
                    colors: [
                        Color(red: 0.104, green: 0.079, blue: 0.147),
                        Color(red: 0.063, green: 0.055, blue: 0.105),
                        Color(red: 0.051, green: 0.051, blue: 0.094)
                    ], startPoint: .topLeading, endPoint: .bottomTrailing
                ).ignoresSafeArea()
            )
            .tint(Color(red: 170.0/255, green: 150.0/255, blue: 1.0))
            .onAppear { pairing.refreshStoredState() }
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("닫기") { dismiss() }
                }
            }
        }
    }
}
