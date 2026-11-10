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

    @Published private(set) var phase = "준비됨"
    @Published private(set) var pin: String?
    @Published private(set) var active = false
    @Published private(set) var verified = false
    @Published private(set) var failureReason: String?
    private var service: NetService?
    private var backgroundTask: BGContinuedProcessingTask?
    private var waitingForHost = false
    private var taskFinished = false
    private var currentServicePort: UInt16 = 0

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
        active = true
        verified = false
        failureReason = nil
        pin = nil
        phase = "로컬 네트워크 권한 및 무선 페어링 준비"
        ScarletDiagnosticRecorder.shared.record(
            "pairing", "pairing_started", fields: ["method": "on_device_rppairing"])
        Task {
            _ = try? await UNUserNotificationCenter.current()
                .requestAuthorization(options: [.alert, .sound])
            guard active else { return }
            phase = "연결 대기 중 · 설정 → 개인정보 보호 및 보안 → 개발자 모드"
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
                        self.phase = "백그라운드 연결 유지가 종료됨"
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
                self.phase = "백그라운드 연결 유지가 종료됨"
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
                    self.phase = "내장 SideStore에 페어링 등록 및 연결 검증"
                    self.backgroundTask?.progress.completedUnitCount = 70
                    let (ok, reason) = await ScarletNativePairingInstaller.install(
                        candidate: bytes)
                    self.verified = ok
                    self.failureReason = ok ? nil : reason
                    self.phase = ok ? "페어링 완료 · SideStore 연결 검증됨"
                                    : "페어링 생성됨 · SideStore 연결 검증 실패"
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
                    self.failureReason = nonSensitiveFailure ?? "empty_pairing_file"
                    self.phase = "기기 페어링 실패"
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
        phase = "iPhone 설정에서 ‘Scarlet Crystal’ 선택"
        ScarletDiagnosticRecorder.shared.record(
            "pairing", "bonjour_host_advertising")
    }

    fileprivate func showPIN(_ value: String) {
        guard active else { return }
        pin = value
        phase = "설정에서 PIN 입력"
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
        phase = "로컬 네트워크 광고 실패 · 앱 네트워크 권한 확인"
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
struct ScarletDevicePairingSheet: View {
    @ObservedObject private var pairing = ScarletDevicePairingModel.shared
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Form {
                Section("연결") {
                    Label(pairing.phase, systemImage:
                        pairing.verified ? "checkmark.seal.fill"
                        : pairing.active ? "waveform.path"
                        : "antenna.radiowaves.left.and.right")
                    if pairing.active {
                        ProgressView()
                        Text("설정 → 개인정보 보호 및 보안 → 개발자 모드 → Scarlet Crystal과 페어링")
                            .font(.footnote)
                        Text("PIN은 Scarlet 알림으로 표시됩니다. 알림을 허용하세요.")
                            .font(.footnote)
                    }
                    if let pin = pairing.pin {
                        LabeledContent("페어링 PIN", value: pin)
                    }
                    if let reason = pairing.failureReason {
                        LabeledContent("연결 오류", value: reason)
                    }
                    if pairing.verified {
                        Text("기존 SideStore 갱신 엔진과 연결이 확인됐습니다.")
                    }
                    Button {
                        pairing.begin()
                    } label: {
                        Label(pairing.active ? "페어링 진행 중" : "기기 페어링 시작",
                              systemImage: "iphone.gen3.radiowaves.left.and.right")
                    }
                    .disabled(pairing.active)
                    .accessibilityIdentifier("SCARLET_NATIVE_RPPAIR_START")
                }
                Section {
                    Text("새 페어링이 연결 검증에 실패하면 기존 SideStore 페어링 파일은 유지됩니다. 인증서와 게스트 앱도 변경하지 않습니다.")
                        .font(.footnote)
                }
            }
            .navigationTitle("기기 페어링")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("닫기") { dismiss() }
                }
            }
        }
    }
}
