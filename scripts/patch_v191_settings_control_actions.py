#!/usr/bin/env python3
"""V191 settings interaction diagnostic: isolate local tap from SideStore XPC.

No new navigation/gesture overlay. The local test works even when no pairing
or service exists. Service-dependent toggles remain fail-closed but explain
why they cannot be changed and provide a manual read retry.

The patch is allowlisted and idempotent, not a wholesale settings rewrite.
"""
from pathlib import Path
import sys

MARK="SCARLET_V191_SETTINGS_ACTION_DIAGNOSTICS"
SHELL=Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
SETTINGS=Path("LiveContainerSwiftUI/Views/Settings/LCSettingsView.swift")


def once(s, old, new, label):
    n=s.count(old)
    if n!=1: raise ValueError(f"settings {label}: expected one anchor, found {n}")
    return s.replace(old,new,1)


def patch_shell(s):
    if MARK in s:
        for key in ("settings.local_touch", "settings.sidestore_retry", "settings.toggle_read_failed",
                    "Local touch events:", "Retry SideStore settings",
                    "Settings could not be read from SideStore"):
            if key not in s: raise ValueError("settings patch partially applied: "+key)
        if s.count(MARK)!=1: raise ValueError("settings patch marker count")
        return s
    if "SCARLET_V183_HOST_LOG_FALLBACK" not in s or "struct V3AccountSettings: View {" not in s:
        raise ValueError("host logs and embedded V3 settings required")
    s=once(s,
        '    case logsOpened = "logs.opened"\n',
        '    case logsOpened = "logs.opened"\n'
        f'    // {MARK}: fixed button-action outcomes, no user values or keys.\n'
        '    case settingsLocalTouch = "settings.local_touch"\n'
        '    case settingsSideStoreRetry = "settings.sidestore_retry"\n'
        '    case settingsToggleReadFailed = "settings.toggle_read_failed"\n'
        '    case settingsLocalClearNotifications = "settings.local_clear_notifications"\n',
        "host log event allowlist")
    s=once(s,
        'struct V3AccountSettings: View {\n    @EnvironmentObject private var status: V3SideStoreStatusStore\n',
        'struct V3AccountSettings: View {\n'
        '    @EnvironmentObject private var status: V3SideStoreStatusStore\n'
        '    @State private var localTouchEvents = 0\n',
        "local settings test state")
    s=once(s,
        '    var body: some View {\n        Section("Setup") {\n',
        '''    var body: some View {
        // This test is deliberately local. No SideStore RPC, App Group,
        // Apple login or pairing can prevent its on-tap state mutation.
        Section("Settings Controls Diagnostic") {
            Button("Test local settings button") {
                localTouchEvents += 1
                ScarletV183HostLog.record(.settingsLocalTouch)
            }
            Text("Local touch events: \\(localTouchEvents)")
                .font(.caption).foregroundColor(.secondary)
            if !status.connected || status.isStale {
                Text("SideStore status unavailable. Its controls may be disabled; local controls should still work.")
                    .font(.caption).foregroundColor(.orange)
            }
            Button("Retry SideStore status") {
                ScarletV183HostLog.record(.settingsSideStoreRetry)
                status.reload(manual: true)
            }
        }
        Section("Setup") {
''',
        "separate local and service button diagnostic")

    # Keep the service-backed toggle fail-closed, but show a genuine
    # explanation and a user-controlled retry instead of a dead-looking row.
    start=s.index("struct V3BoolSettingRow: View {")
    stop=s.index("\nprivate struct V3SourceAddFailure {",start)
    part=s[start:stop]
    part=once(part,
        '    @State private var loaded = false\n',
        '    @State private var loaded = false\n'
        '    @State private var loadFailure = false\n',
        "toggle load failure state")
    part=once(part,
        '''    var body: some View {
        Toggle(isOn: Binding(get: { value }, set: { value = $0; save($0) })) {
            Label(title, systemImage: icon)
        }
        .disabled(status.isStale || !loaded)
        .task { await load() }
    }
''',
        '''    var body: some View {
        VStack(alignment: .leading, spacing: 5) {
            Toggle(isOn: Binding(get: { value }, set: { value = $0; save($0) })) {
                Label(title, systemImage: icon)
            }
            .disabled(status.isStale || !loaded || loadingRequest)
            if status.isStale || !loaded {
                Text(loadFailure
                    ? "Settings could not be read from SideStore"
                    : "SideStore status unavailable; this setting is not editable")
                    .font(.caption2).foregroundColor(.orange)
                Button("Retry SideStore settings") {
                    ScarletV183HostLog.record(.settingsSideStoreRetry)
                    Task { await load() }
                }
                .font(.caption)
                .disabled(loadingRequest)
            }
        }
        .task { await load() }
    }
''',
        "disabled setting reason and read retry")
    part=once(part,
        '''        loadingRequest = true
        defer { loadingRequest = false }
        do {
            let reply = try await V3ServiceBridge.shared.request(operation: "settingsGet")
            if let bools = reply["bools"] as? [String: Bool], let current = bools[key] {
                value = current
                confirmedValue = current
            } else if let legacy = status.settings[key] {
                value = legacy
                confirmedValue = legacy
            }
            loaded = true
        } catch { status.present(error) }
''',
        '''        loadingRequest = true
        loadFailure = false
        defer { loadingRequest = false }
        do {
            let reply = try await V3ServiceBridge.shared.request(
                operation: "settingsGet", requestDeadline: Date().addingTimeInterval(15))
            if let bools = reply["bools"] as? [String: Bool], let current = bools[key] {
                value = current
                confirmedValue = current
                loaded = true
            } else if let legacy = status.settings[key] {
                value = legacy
                confirmedValue = legacy
                loaded = true
            } else {
                // A reply without an authoritative value is NOT a successful
                // read. Never enable a toggle with a fabricated false value.
                loaded = false
                loadFailure = true
                ScarletV183HostLog.record(.settingsToggleReadFailed)
            }
        } catch {
            loaded = false
            loadFailure = true
            ScarletV183HostLog.record(.settingsToggleReadFailed)
            status.present(error)
        }
''',
        "true read result only, not missing key as false")
    s=s[:start]+part+s[stop:]
    if patch_shell(s)!=s: raise ValueError("settings shell patch not idempotent")
    return s


def patch_settings(s):
    token='    func clearNotifications() {\n'
    new='''    func clearNotifications() {
        ScarletV183HostLog.record(.settingsLocalClearNotifications)
'''
    if new in s: return s
    if "struct LCSettingsView: View {" not in s:
        raise ValueError("LiveContainer settings source drifted")
    return once(s,token,new,"local clear notifications event")


def apply(root:Path):
    files=(root/SHELL,root/SETTINGS)
    if any(not f.is_file() or f.is_symlink() for f in files):
        raise ValueError("compiled host/settings files missing")
    old=[p.read_text(encoding="utf8") for p in files]
    new=[patch_shell(old[0]),patch_settings(old[1])]
    if patch_shell(new[0])!=new[0] or patch_settings(new[1])!=new[1]:
        raise ValueError("non-idempotent settings patch")
    for path,before,after in zip(files,old,new):
        if before!=after:path.write_text(after,encoding="utf8")
    print("[PASS] independent local settings touch receipt, SideStore read retry and error reasons")
    print("[SAFE] no removal of guest data, credentials, App Groups or Liquid Glass")
    print("[UNVERIFIED] iPhone hit-testing and every existing settings control still require device testing")


if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v191_settings_control_actions.py <LiveContainer>")
    apply(Path(sys.argv[1]))
