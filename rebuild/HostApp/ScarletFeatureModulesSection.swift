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
            Toggle("멀티탭 전환 애니메이션", isOn: $switcherMotion)
                .disabled(!sharedStorageAvailable)
                .accessibilityIdentifier("SCARLET_MODULE_SWITCHER_MOTION")
            Toggle("멀티탭 진동 피드백", isOn: $switcherHaptics)
                .disabled(!sharedStorageAvailable)
                .accessibilityIdentifier("SCARLET_MODULE_SWITCHER_HAPTICS")
        } header: {
            Text("멀티탭")
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
