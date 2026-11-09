// Scarlet Crystal feature modules. These modules compile into the ONE host;
// they do not create additional Apple App IDs, extensions or dynamically
// executable unsigned code. Essential signing/runtime modules stay enabled.
import SwiftUI
import UIKit

@available(iOS 17.0, *)
enum ScarletFeatureModulePreferences {
    static let switcherMotionKey = "Scarlet.Feature.SwitcherMotion.V1"
    static let switcherHapticsKey = "Scarlet.Feature.SwitcherHaptics.V1"
    static let defaults = LCUtils.appGroupUserDefault
    static func enabled(_ key: String) -> Bool {
        guard let stored = defaults.object(forKey: key) as? Bool else {
            return true // preserve the existing visual/haptic experience
        }
        return stored
    }
}

@available(iOS 17.0, *)
struct ScarletFeatureModulesSection: View {
    @AppStorage("Scarlet.Feature.SwitcherMotion.V1",
                store: LCUtils.appGroupUserDefault)
    private var switcherMotion = true
    @AppStorage("Scarlet.Feature.SwitcherHaptics.V1",
                store: LCUtils.appGroupUserDefault)
    private var switcherHaptics = true

    private var sharedStorageAvailable: Bool {
        FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: LCSharedUtils.appGroupID()
        ) != nil
    }

    var body: some View {
        Section {
            LabeledContent("Liquid Glass", value: "호스트 내장 · 항상 활성")
                .accessibilityIdentifier("SCARLET_MODULE_NATIVE_GLASS")
            LabeledContent("앱 실행 엔진", value: "LiveContainer · LiveProcess")
                .accessibilityIdentifier("SCARLET_MODULE_GUEST_ENGINE")
            Toggle("멀티탭 전환 애니메이션", isOn: $switcherMotion)
                .disabled(!sharedStorageAvailable)
                .accessibilityIdentifier("SCARLET_MODULE_SWITCHER_MOTION")
            Toggle("멀티탭 진동 피드백", isOn: $switcherHaptics)
                .disabled(!sharedStorageAvailable)
                .accessibilityIdentifier("SCARLET_MODULE_SWITCHER_HAPTICS")
            LabeledContent("모듈 설정 공유",
                value: sharedStorageAvailable ? "App Group 접근 가능" : "App Group 접근 불가")
            LabeledContent("서명 App ID", value: "빌드 타깃 4개 · 기기 권한 별도 확인")
                .accessibilityIdentifier("SCARLET_MODULE_APPID_FOOTPRINT")
            LabeledContent("세션 유지",
                value: "기존 LiveProcess만 재개 · 일반 게스트는 재실행")
                .accessibilityIdentifier("SCARLET_MODULE_SESSION_TRUTH")
        } header: {
            Text("기능 모듈")
        } footer: {
            Text("내장 UI 기능은 App ID를 추가하지 않습니다. 시스템 확장 3개는 그대로 유지합니다. Liquid Glass·서명 엔진·기존 게스트 데이터는 변경하지 않습니다.")
        }
        .onChange(of: switcherMotion) { value in
            ScarletDiagnosticRecorder.shared.record(
                "module", "switcher_motion_changed",
                fields: ["state": value ? "enabled" : "disabled"])
        }
        .onChange(of: switcherHaptics) { value in
            ScarletDiagnosticRecorder.shared.record(
                "module", "switcher_haptics_changed",
                fields: ["state": value ? "enabled" : "disabled"])
        }
    }
}
