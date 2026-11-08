#!/usr/bin/env python3
"""Inject a fresh Scarlet host into pinned upstream LiveContainer, fail closed.

Only new project's UI/core and protected V131 native glass adapter are copied.
Do not apply previous V-series patches or edit LC/SideStore signing assets.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def instrument_original_guest_signing(engine: Path) -> dict:
    """Trace the *original* LC signing step without changing sign/launch logic.

    Swift.String errors otherwise flatten into NSError(domain=Swift.String,
    code=1), concealing whether the launcher failed before opening a scene.
    Categorize expected upstream signing errors; never export the raw
    localized string, bundle path, app name or identity.
    """
    target = engine / "LiveContainerSwiftUI/Models/LCAppModel.swift"
    assert target.is_file(), "Pinned LC guest model missing"
    source = target.read_text()
    assert '"signing_started"' not in source and '"signing_reason"' not in source, (
        "LC guest signing diagnostics already injected")
    original = "        try await signApp(force: false)\n"
    assert source.count(original) == 1, "Pinned LC runApp signing step changed"
    source = source.replace(original, """        ScarletDiagnosticRecorder.shared.record("guest", "signing_started")
        do {
            try await signApp(force: false)
            ScarletDiagnosticRecorder.shared.record("guest", "signing_completed", status: "success")
        } catch {
            ScarletDiagnosticRecorder.shared.recordError("guest", "signing_failed", error: error)
            throw error
        }
""")
    err_anchor = "                throw signError.loc\n"
    assert source.count(err_anchor) == 1, "Pinned LC signing error pathway changed"
    source = source.replace(err_anchor, """                let safeReason: String
                let detail = signError.lowercased()
                if detail.contains("nocertificatefound") {
                    safeReason = "certificate_missing"
                } else if detail.contains("latestcertificateinvalid") {
                    safeReason = "certificate_invalid"
                } else if detail.contains("encrypted") {
                    safeReason = "encrypted_binary"
                } else if detail.contains("entitlement") {
                    safeReason = "entitlements"
                } else if detail.contains("certificate") {
                    safeReason = "certificate_error"
                } else {
                    safeReason = "other_sign_error"
                }
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "signing_reason", status: "error",
                    fields: ["reason": safeReason])
                // Do not retry with a demonstrably bad signing setup.
                // The original LC Settings offers safe import/refresh and
                // JIT-Less validation. No certificate is deleted or replaced.
                if safeReason == "certificate_invalid" ||
                    safeReason == "certificate_missing" {
                    NotificationCenter.default.post(
                        name: Notification.Name("ScarletGuestCertificateInvalid"),
                        object: nil)
                }
                throw signError.loc
""")
    target.write_text(source)
    return {"originalLCSigningUnchanged": True,
            "originalLCLauncherUnchanged": True,
            "signingPhaseLogged": True,
            "safeFailureCategoryLogged": True,
            "sha256": file_sha(target)}


def apply_figma_app_icon(root: Path, engine: Path) -> dict:
    """Build native AppIcon assets from the exact Figma artwork, before actool.

    No host signing assets, app identifiers, guest data or alternate-icon
    catalog entries are removed. macOS sips ships with the Xcode runner.
    """
    source=root/"rebuild/assets/ScarletCrystalAppIcon.figma.png.base64"
    assert source.is_file(), "Figma icon artwork is missing"
    png=base64.b64decode(source.read_text().strip(), validate=True)
    assert png.startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG signature"
    width,height=struct.unpack(">II",png[16:24])
    assert width>=512 and height>=512 and width==height, (width,height)
    iconset=engine/"Resources/Assets.xcassets/AppIcon.appiconset"
    assert iconset.is_dir(), "Pinned upstream app icon catalog missing"
    manifest=json.loads((iconset/"Contents.json").read_text())
    names=sorted({x["filename"] for x in manifest["images"] if x.get("filename")})
    assert "AppIcon1024.png" in names, "Native primary icon entry missing"
    assert all((iconset/n).is_file() for n in names), "Pinned native icon catalog drift"
    import os
    with tempfile.TemporaryDirectory(prefix="scarlet-figma-icon-") as tmp:
        original=Path(tmp)/"Figma-Icon.png"
        original.write_bytes(png)
        for name in names:
            destination=iconset/name
            subprocess.run(["sips","-s","format","png","-z","1024","1024",
                            str(original),"--out",str(destination)],
                           check=True, stdout=subprocess.DEVNULL)
            output=destination.read_bytes()
            assert output.startswith(b"\x89PNG\r\n\x1a\n")
            assert struct.unpack(">II",output[16:24])==(1024,1024)
    return {"sourceFigmaNode":"108:2","inputPixels":[width,height],
            "primaryIcon":"AppIcon1024.png","variants":names,
            "assetSHA256":{n:file_sha(iconset/n) for n in names}}


def hide_embedded_sidestore_guest_navigation(engine: Path) -> dict:
    """Retain SideStore/SideSign engines, remove only its *guest UI* shortcuts.

    The user wants the original LiveContainer app manager with IPA/URL import,
    but not a second SideStore application window. Keep SideStoreSupport,
    LiveProcess and refresh IPC untouched. Exact source anchors refuse drift.
    """
    view=engine/"LiveContainerSwiftUI/Views/AppList/LCAppListView.swift"
    assert view.is_file(), "Pinned native LiveContainer app manager missing"
    source=view.read_text()

    # Native toolbar: the first leading item is the real IPA/URL add menu.
    # Only the SECOND item launches the bundled SideStore guest application.
    toolbar_start="""                ToolbarItem(placement: .topBarLeading) {
                    if(UserDefaults.sideStoreExist()) {
"""
    next_item="""                ToolbarItem(placement: .topBarTrailing) {
"""
    assert source.count(toolbar_start)==1, "Native SideStore guest toolbar changed"
    prefix, remainder=source.split(toolbar_start,1)
    assert remainder.count(next_item)>=1, "Native guest toolbar end changed"
    removed, rest=remainder.split(next_item,1)
    for expected in ("LCUtils.openSideStore(delegate: self)",
                     "BuiltInSideStoreAppInfo.shared.iconIsDarkIcon"):
        assert removed.count(expected)==1, f"Native SideStore guest button changed: {expected}"
    source=prefix+next_item+rest
    assert 'Button("lc.appList.installFromIpa".loc' in source
    assert 'Button("lc.appList.installFromUrl".loc' in source

    # No hidden secondary path via the guest launch ID or SideStore URL.
    builtin="""        if appFound == nil && bundleId == "builtinSideStore" {
            appFound = LCAppModel(appInfo: BuiltInSideStoreAppInfo.shared)
        }
"""
    assert source.count(builtin)==1, "Pinned builtin SideStore guest launch changed"
    source=source.replace(builtin,"")

    deeplink="""        if url.scheme == "sidestore" && UserDefaults.sideStoreExist() {
            UserDefaults.standard.setValue(url.absoluteString, forKey: "launchAppUrlScheme")
            LCUtils.openSideStore(delegate: self)
            return
        }
"""
    assert source.count(deeplink)==1, "Pinned SideStore deeplink route changed"
    source=source.replace(deeplink,
        '        if url.scheme == "sidestore" {\n'
        '            NSLog("[SCARLET_ROUTE] SideStore guest UI disabled; engine retained")\n'
        '            return\n'
        '        }\n')
    assert "LCUtils.openSideStore(" not in source
    assert "BuiltInSideStoreAppInfo.shared" not in source

    # Keep the original manager and importer. Trace important lifecycle
    # boundaries without logging any file paths, URLs or app identifiers.
    native_events={
        "    func startInstallApp(_ fileUrl:URL) async {\n":
        '    func startInstallApp(_ fileUrl:URL) async {\n'
        '        ScarletDiagnosticRecorder.shared.record("guest_import", "file_import_requested")\n',
        "            try await installIpaFile(fileUrl)\n":
        '            try await installIpaFile(fileUrl)\n'
        '            ScarletDiagnosticRecorder.shared.record("guest_import", "import_pipeline_completed",\n'
        '                fields: ["result": "launch_unverified"])\n',
        "        } catch {\n            errorInfo = error.localizedDescription\n":
        '        } catch {\n'
        '            ScarletDiagnosticRecorder.shared.recordError("guest_import", "import_pipeline_failed", error: error)\n'
        '            errorInfo = error.localizedDescription\n',
        "    func startInstallFromUrl() async {\n":
        '    func startInstallFromUrl() async {\n'
        '        ScarletDiagnosticRecorder.shared.record("guest_import", "url_import_requested")\n'
    }
    for original,patched in native_events.items():
        assert source.count(original)>=1, "Pinned LC import tracer anchor missing: "+repr(original)
        # 'catch/errorInfo' may appear in multiple functions; trace only
        # the local startInstallApp() catch, not unrelated error handlers.
        if original.startswith("        } catch {"):
            region_start=source.index("    func startInstallApp(_ fileUrl:URL) async {")
            region_end=source.index("    nonisolated func decompress(",region_start)
            region=source[region_start:region_end]
            assert region.count(original)==1, "Pinned importer catch changed"
            source=source[:region_start]+region.replace(original,patched)+source[region_end:]
        else:
            assert source.count(original)==1, "Pinned LC import tracer duplicate: "+repr(original)
            source=source.replace(original,patched)
    # Upstream deliberately keeps an imported guest when signing fails.
    # A returned importer is *not* proof of a runnable, signed application.
    # Emit a bounded failure class; do not put the user-facing signing error,
    # app name, IPA path or certificate details in diagnostic JSONL.
    sign_marker = "        // we leave it unsigned even if signing failed\n        if let signError {\n"
    assert source.count(sign_marker) == 1, "Pinned LC import signing pathway changed"
    sign_patch = """        // we leave it unsigned even if signing failed
        if let signError {
            if !signSuccess {
                scarletGuestImportSignFailed = true
                let sourceError = signError.lowercased()
                let reason: String
                if sourceError.contains("nocertificatefound") {
                    reason = "certificate_missing"
                } else if sourceError.contains("latestcertificateinvalid") {
                    reason = "certificate_invalid"
                } else if sourceError.contains("encrypted") {
                    reason = "encrypted_binary"
                } else if sourceError.contains("entitlement") {
                    reason = "entitlements"
                } else {
                    reason = "other_sign_error"
                }
                ScarletDiagnosticRecorder.shared.record("guest_import",
                    "import_signing_failed", status: "error",
                    fields: ["reason": reason])
            }
"""
    source = source.replace(sign_marker, sign_patch)
    # The Scarlet + button presents Files directly, never LC's app-list page.
    # Only the existing LC import/replace/signing state machine is retained.
    # The original manager remains available to original LC entry points,
    # but it is not presented during any Scarlet IPA selection or installation.
    importer_init="""    init() {
        _installOptions = State(initialValue: [])
    }
"""
    importer_new="""    private let scarletQueuedIPAURL: URL?
    private let scarletOnImportFinished: (() -> Void)?
    @State private var scarletDidStartQueuedImport = false
    @State private var scarletQueuedImportFinished = false
    @State private var scarletGuestImportSignFailed = false

    init(scarletQueuedIPAURL: URL? = nil,
         scarletOnImportFinished: (() -> Void)? = nil) {
        self.scarletQueuedIPAURL = scarletQueuedIPAURL
        self.scarletOnImportFinished = scarletOnImportFinished
        _installOptions = State(initialValue: [])
    }
"""
    assert source.count(importer_init) == 1, "Pinned LC importer initializer changed"
    source = source.replace(importer_init, importer_new)

    begin = """        NavigationView {
            ScrollView {
"""
    replacement = """        NavigationView {
            if let queuedIPA = scarletQueuedIPAURL {
                VStack(spacing: 20) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 21, style: .continuous)
                            .fill(Color(red: 0.39, green: 0.31, blue: 0.65).opacity(0.32))
                            .frame(width: 72, height: 72)
                        Image(systemName: scarletGuestImportSignFailed
                              ? "exclamationmark.shield.fill"
                              : "shippingbox.fill")
                            .font(.system(size: 31, weight: .medium))
                            .foregroundStyle(Color(red: 0.76, green: 0.67, blue: 1))
                    }
                    VStack(spacing: 7) {
                        Text(scarletQueuedImportFinished
                             ? (scarletGuestImportSignFailed
                                ? "서명 확인이 필요합니다"
                                : "게스트 앱 가져오기 완료")
                             : "게스트 앱 설치")
                            .font(.title3.bold())
                            .foregroundStyle(Color.white)
                        Text(scarletQueuedImportFinished
                             ? (scarletGuestImportSignFailed
                                ? "앱 파일은 가져왔지만 서명은 완료되지 않았습니다."
                                : "실제 실행과 서명 상태는 앱 목록에서 별도로 확인하세요.")
                             : "LiveContainer에서 IPA를 가져오는 중입니다.")
                            .font(.subheadline)
                            .foregroundStyle(Color(red: 0.76, green: 0.73, blue: 0.84))
                            .multilineTextAlignment(.center)
                            .accessibilityIdentifier("SCARLET_GUEST_IMPORT_STAGE")
                    }
                    ProgressView(value: Double(installProgressPercentage), total: 1.0)
                        .tint(Color(red: 0.76, green: 0.67, blue: 1))
                        .accessibilityIdentifier("SCARLET_GUEST_IMPORT_ACTUAL_PROGRESS")
                    if !scarletQueuedImportFinished {
                        Text("앱 데이터를 보존하면서 가져오기와 서명 검증을 진행합니다.")
                            .font(.caption)
                            .multilineTextAlignment(.center)
                            .foregroundStyle(Color(red: 0.68, green: 0.65, blue: 0.75))
                    }
                    Button("닫기") {
                        scarletOnImportFinished?()
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(Color(red: 0.44, green: 0.33, blue: 0.77))
                    .disabled(!scarletQueuedImportFinished || installprogressVisible)
                    .accessibilityIdentifier("SCARLET_IMPORT_PROGRESS_CLOSE")
                }
                .padding(24)
                .frame(maxWidth: 350)
                .background {
                    if #available(iOS 26.0, *) {
                        RoundedRectangle(cornerRadius: 28, style: .continuous)
                            .fill(.clear)
                            .glassEffect()
                    } else {
                        RoundedRectangle(cornerRadius: 28, style: .continuous)
                            .fill(.ultraThinMaterial)
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(LinearGradient(
                    colors: [Color(red: 0.104, green: 0.079, blue: 0.147),
                             Color(red: 0.051, green: 0.051, blue: 0.094)],
                    startPoint: .topLeading, endPoint: .bottomTrailing).ignoresSafeArea())
                .onAppear {
                    guard !scarletDidStartQueuedImport else { return }
                    scarletDidStartQueuedImport = true
                    if !didAppear { onAppear() }
                    Task {
                        await startInstallApp(queuedIPA)
                        scarletQueuedImportFinished = true
                    }
                }
                .accessibilityIdentifier("SCARLET_GUEST_IMPORT_PROGRESS_ONLY")
                .accessibilityIdentifier("SCARLET_BRANDED_GUEST_IMPORT_CARD")
            } else {
                ScrollView {
"""
    assert source.count(begin) == 1, "Pinned LC app manager body changed"
    source = source.replace(begin, replacement)
    end = """        }
        .navigationViewStyle(StackNavigationViewStyle())
"""
    assert source.count(end) == 1, "Pinned LC NavigationView close changed"
    source = source.replace(end, """            }
        }
        .navigationViewStyle(StackNavigationViewStyle())
""")

    # The existing betterFileImporter, replacement confirmation and errors
    # remain attached to NavigationView; the queued branch never shows ScrollView.
    assert source.count("SCARLET_GUEST_IMPORT_PROGRESS_ONLY") == 1
    assert '.betterFileImporter(isPresented: $choosingIPA' in source
    assert 'try await installIpaFile(fileUrl)' in source
    view.write_text(source)
    return {"appManager":"LCAppListView",
            "nativeIPAImportPreserved":True,
            "scarletFilesPickerOwnedByHost":True,
            "scarletAppListNotPresentedDuringImport":True,
            "nativeURLImportPreserved":True,
            "embeddedSideStoreGuestNavigationRemoved":True,
            "embeddedSideStoreEnginePreserved":True,
            "changedFile":str(view.relative_to(engine)),
            "patchedFileSHA256":file_sha(view)}


def theme_native_settings_section_rows(source: str) -> tuple[str, int]:
    """Match Figma card tint on all upstream settings rows without changing actions.

    Pinned LCSettingsView contains 15 real sections; Scarlet adds one
    login/diagnostics section. Exact 16-section count is a drift guard.
    """
    import re
    output = []
    active_section_indents = []
    started = 0
    styled = 0
    for line in source.splitlines(keepends=True):
        start = re.match(r"^( {16}| {20})Section\s*\{", line)
        if start:
            active_section_indents.append(len(start.group(1)))
            started += 1
        output.append(line)
        end = re.fullmatch(r"( {16}| {20})\}\s*", line)
        if end and active_section_indents:
            indent = len(end.group(1))
            if indent == active_section_indents[-1]:
                active_section_indents.pop()
                output.append(" " * indent +
                    ".listRowBackground(Color(red: 36.0/255, green: 35.0/255, blue: 58.0/255).opacity(0.80))\n")
                styled += 1
    assert started == 16 and styled == 16 and not active_section_indents, (
        "Pinned LC settings Section structure changed", started, styled,
        active_section_indents)
    return "".join(output), styled


def attach_native_settings_diagnostics(engine: Path) -> dict:
    """Add one diagnostics entry to the ORIGINAL full-screen LCSettingsView.

    Never replace its navigation/Form, JIT controls, storage, certificate
    storage, app groups, or settings persistence. Use fail-closed pinned
    anchors to avoid silently corrupting future upstream revisions.
    """
    target=engine/"LiveContainerSwiftUI/Views/Settings/LCSettingsView.swift"
    assert target.is_file(), "Pinned LC settings view missing"
    source=target.read_text()
    state_anchor="struct LCSettingsView: View {\n"
    form_anchor="        NavigationView {\n            Form {\n"
    style_anchor="        .navigationViewStyle(StackNavigationViewStyle())\n"
    for anchor in (state_anchor,form_anchor,style_anchor):
        assert source.count(anchor)==1, "Pinned settings structure changed: "+repr(anchor)
    source=source.replace(state_anchor, state_anchor+
        '    @State private var scarletShowAppleLogin = false\n'
        '    @State private var scarletLoginVerified: Bool? = nil\n')
    new_section="""        NavigationView {
            Form {
                Section {
                    Button {
                        ScarletDiagnosticRecorder.shared.record("auth", "open_from_settings")
                        scarletShowAppleLogin = true
                    } label: {
                        Label(scarletLoginVerified == true ? "Apple ID 로그인됨 · 계정 관리" :
                              (scarletLoginVerified == nil ? "Apple ID 확인 중" : "Apple ID 로그인"),
                              systemImage: scarletLoginVerified == true ? "checkmark.seal.fill" : "person.crop.circle")
                    }
                    .accessibilityIdentifier("SCARLET_SETTINGS_NATIVE_APPLE_LOGIN")
                    Text(scarletLoginVerified == true ? "인증 세션 복원됨 · 서명 인증서는 별도 확인" :
                         (scarletLoginVerified == nil ? "저장된 로그인 상태 확인 중" : "저장된 로그인 세션 없음"))
                        .font(.footnote)
                        .foregroundStyle(scarletLoginVerified == true ? Color.green : Color.secondary)
                    if #available(iOS 16.0, *) {
                        NavigationLink {
                            ScarletDiagnosticLogView()
                        } label: {
                            Label("진단 로그 보기 및 공유", systemImage: "ladybug")
                        }
                        .accessibilityIdentifier("SCARLET_NATIVE_DIAGNOSTICS_ENTRY")
                    }
                } header: {
                    Text("Scarlet Crystal")
                } footer: {
                    Text("실행 오류, 게스트 앱 동작, 엔진 상태를 기기 안에서 기록하고 공유할 수 있습니다.")
                }
"""
    source=source.replace(form_anchor,new_section)
    source=source.replace(style_anchor,style_anchor+
        '        .sheet(isPresented: $scarletShowAppleLogin, onDismiss: {\n'
        '            Task { @MainActor in\n'
        '                if #available(iOS 17.0, *) {\n'
        '                    scarletLoginVerified = await ScarletConnectedSideSignEngine().storedAuthenticated()\n'
        '                }\n'
        '            }\n'
        '        }) {\n'
        '            if #available(iOS 17.0, *) {\n'
        '                ScarletAppleIDLoginSheet(engine: ScarletConnectedSideSignEngine())\n'
        '            } else {\n'
        '                Text("Apple 로그인은 iOS 17 이상에서 제공됩니다.")\n'
        '            }\n'
        '        }\n'
        '        .onAppear {\n'
        '            ScarletDiagnosticRecorder.shared.record("settings", "native_form_visible")\n'
        '            Task { @MainActor in\n'
        '                if #available(iOS 17.0, *) {\n'
        '                    scarletLoginVerified = await ScarletConnectedSideSignEngine().storedAuthenticated()\n'
        '                }\n'
        '            }\n'
        '        }\n'
        '        .onReceive(NotificationCenter.default.publisher(\n'
        '            for: Notification.Name("ScarletGuestAuthVerified"))) { _ in\n'
        '            Task { @MainActor in\n'
        '                if #available(iOS 17.0, *) {\n'
        '                    scarletLoginVerified = await ScarletConnectedSideSignEngine().storedAuthenticated()\n'
        '                }\n'
        '            }\n'
        '        }\n'
        '        .onChange(of: dynamicColors) { enabled in\n'
        '            ScarletDiagnosticRecorder.shared.record("settings", "dynamic_colors_changed",\n'
        '                fields: ["state": enabled ? "enabled" : "disabled"])\n'
        '        }\n'
        '        .onChange(of: darkModeIcon) { enabled in\n'
        '            ScarletDiagnosticRecorder.shared.record("settings", "dark_icon_changed",\n'
        '                fields: ["state": enabled ? "enabled" : "disabled"])\n'
        '        }\n'
        '        .onChange(of: JITEnabler) { _ in\n'
        '            ScarletDiagnosticRecorder.shared.record("settings", "jit_provider_changed")\n'
        '        }\n')
    form_style_anchor = '            }\n            .navigationBarTitle("lc.tabView.settings".loc)\n'
    assert source.count(form_style_anchor) == 1, "Pinned LC settings Form changed"
    source = source.replace(form_style_anchor,
        '            }\n'
        '            .scarletNativeListTheme()\n'
        '            .scarletDockScrollClearance()\n'
        '            .navigationBarTitle("lc.tabView.settings".loc)\n')
    source, styled_rows = theme_native_settings_section_rows(source)
    target.write_text(source)
    return {"settings":"original-LCSettingsView","styledSections":styled_rows,"singleTitle":True,
            "diagnosticSectionAtTop":True,"nativeLoginEntry":True,
            "newSettingsSheetCreated":False,"sha256":file_sha(target)}


def apply_scarlet_native_tweaks_theme(engine: Path) -> dict:
    """Theme the pinned original tweak List without touching toggle/import logic."""
    target = engine/"LiveContainerSwiftUI/Views/LCTweaksView.swift"
    assert target.is_file(), "Pinned tweak manager missing"
    source = target.read_text()
    anchor = '''            }
        }
        .navigationTitle(isRoot ? "lc.tabView.tweaks".loc : baseUrl.lastPathComponent)
'''
    assert source.count(anchor) == 1, "Pinned native tweaks List changed"
    styled = '''            }
            .listRowBackground(Color(red: 36.0/255, green: 35.0/255, blue: 58.0/255).opacity(0.80))
        }
        .scarletNativeListTheme()
        .scarletDockScrollClearance()
        .navigationTitle(isRoot ? "lc.tabView.tweaks".loc : baseUrl.lastPathComponent)
'''
    target.write_text(source.replace(anchor, styled))
    return {"tweaks": "original-LCTweaksView", "originalActionsPreserved": True,
            "scarletColorsApplied": True, "sha256": file_sha(target)}


def attach_jitless_diagnostic_scroll_margins(engine: Path) -> dict:
    """Fix the ORIGINAL nested JIT-Less/Entitlement Forms, not just Settings.

    The previous outer NavigationView inset never reached the pushed Form.
    Keep every certificate, test, entitlement, button and action untouched.
    """
    path = engine / "LiveContainerSwiftUI/Views/Settings/LCJITLessDiagnoseView.swift"
    assert path.is_file(), "Pinned LC JIT-Less diagnostic view missing"
    source = path.read_text()
    anchors = (
        '            }\n            .navigationTitle(isLiveProcess ? "LiveProcess Entitlements" : "LiveContainer Entitlements")\n',
        '            }\n            .navigationTitle("lc.settings.jitlessDiagnose".loc)\n',
    )
    for anchor in anchors:
        assert source.count(anchor) == 1, "Pinned nested Form changed: " + repr(anchor)
        source = source.replace(anchor, anchor.replace(
            '            .navigationTitle(', '            .scarletDiagnosticScrollMargins()\n            .navigationTitle('))
    assert source.count(".scarletDiagnosticScrollMargins()") == 2
    path.write_text(source)
    return {"originalNestedForms": 2, "lastRowsCovered": False,
            "source": str(path.relative_to(engine)), "sha256": file_sha(path)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--engine",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    a=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    engine=a.engine
    entry=engine/"LiveContainerSwiftUI/App/LiveContainerSwiftUIApp.swift"
    assert entry.is_file(),"Upstream app entry missing"
    src=entry.read_text()
    original="            LCTabView()\n"
    new="""            Group {
                if #available(iOS 17.0, *) {
                    ScarletIntegratedHostView()
                } else {
                    // Preserve original fallback on older supported iOS.
                    LCTabView()
                }
            }
"""
    if src.count(original)!=1:
        raise RuntimeError("Refuse to overwrite changed upstream app entry")
    out=engine/"LiveContainerSwiftUI/Views/ScarletCrystal"
    if out.exists():raise RuntimeError("ScarletCrystal overlay already present")
    out.mkdir(parents=True)
    sources={
        root/"rebuild/HostApp/ScarletIntegratedHostView.swift":"ScarletIntegratedHostView.swift",
        root/"rebuild/HostApp/ScarletNativeGlass.swift":"ScarletNativeGlass.swift",
        root/"rebuild/HostApp/ScarletGuestSwitcherOverlay.swift":"ScarletGuestSwitcherOverlay.swift",
        root/"rebuild/HostApp/ScarletAppleIDLoginSheet.swift":"ScarletAppleIDLoginSheet.swift",
        root/"rebuild/HostApp/ScarletSideStoreAuthenticationBridge.swift":"ScarletSideStoreAuthenticationBridge.swift",
        root/"rebuild/HostApp/ScarletDiagnosticRecorder.swift":"ScarletDiagnosticRecorder.swift",
        root/"rebuild/Sources/ScarletIndependentUI/ScarletIndependentShell.swift":"ScarletIndependentShell.swift",
        root/"rebuild/Sources/ScarletCleanCore/ScarletActionCoordinator.swift":"ScarletActionCoordinator.swift",
        root/"rebuild/Sources/ScarletCleanCore/ScarletControlAuditTrail.swift":"ScarletControlAuditTrail.swift",
        root/"rebuild/Sources/ScarletCleanCore/ScarletRefreshPolicy.swift":"ScarletRefreshPolicy.swift",
    }
    for inp,name in sources.items():
        assert inp.is_file(),f"Required independent source missing: {inp}"
        shutil.copy2(inp,out/name)
    recorder = out / "ScarletDiagnosticRecorder.swift"
    report_source = recorder.read_text()
    marker = "__SCARLET_BUILD_SHA__"
    assert report_source.count(marker) == 1, "Diagnostic build identity anchor changed"
    runner_sha = os.environ.get("GITHUB_SHA", "").strip()
    build_sha = runner_sha[:12].lower() if re.fullmatch(r"[0-9a-fA-F]{40}", runner_sha) else "local-unverified"
    recorder.write_text(report_source.replace(marker, build_sha))
    figma_icon=apply_figma_app_icon(root,engine)
    # Pinned LiveContainer initialization force-unwraps each persisted guest
    # bundle. A damaged/partial historical guest can otherwise terminate the
    # host before any error screen is displayed. Skip that guest only; NEVER
    # delete or rewrite the bundle, container or shared App Group data.
    src=src.replace(original,new)
    boot_anchor="    init() {\n"
    assert src.count(boot_anchor)==1, "Pinned entry initializer changed"
    src=src.replace(boot_anchor,
        boot_anchor+'        NSLog("[SCARLET_BOOT] phase=app-init-start")\n'
        '        ScarletDiagnosticRecorder.shared.record("boot", "app_init")\n')
    guest_anchors={
        'let newApp = LCAppInfo(bundlePath: "\(LCPath.bundlePath.path)/\(appDir)")!':
        'guard let newApp = LCAppInfo(bundlePath: "\(LCPath.bundlePath.path)/\(appDir)") else {\n'
        '                    NSLog("[SCARLET_BOOT] invalid-local-guest-skipped")\n'
        '                    continue\n'
        '                }',
        'let newApp = LCAppInfo(bundlePath: "\(LCPath.lcGroupBundlePath.path)/\(appDir)")!':
        'guard let newApp = LCAppInfo(bundlePath: "\(LCPath.lcGroupBundlePath.path)/\(appDir)") else {\n'
        '                        NSLog("[SCARLET_BOOT] invalid-shared-guest-skipped")\n'
        '                        continue\n'
        '                    }'
    }
    for before,after in guest_anchors.items():
        assert src.count(before)==1, f"Pinned guest initializer changed: {before}"
        src=src.replace(before,after)
    url_schemes_anchor="tempURLSchemes?.formUnion(newApp.urlSchemes() as! [String])"
    assert src.count(url_schemes_anchor)==2, "Pinned URL scheme loader changed"
    src=src.replace(url_schemes_anchor,
        'if let schemes = newApp.urlSchemes() as? [String] {\n'
        '                        tempURLSchemes?.formUnion(schemes)\n'
        '                    }')
    entry.write_text(src)

    # Mount the sole circular control on an actual running guest scene.  Never
    # place it over the independent host container tabs.  Refuse unknown pins.
    guest_window=engine/"MultitaskSupport/MultitaskAppWindow.swift"
    assert guest_window.is_file(),"Pinned LiveContainer guest window file missing"
    guest_src=guest_window.read_text()
    anchors={
        "        return AppSceneViewController(bundleId: bundleId, dataUUID: dataUUID, delegate: context.coordinator)\n":
        "        guard let controller = AppSceneViewController(bundleId: bundleId, dataUUID: dataUUID, delegate: context.coordinator) else {\n"
        "            return UIViewController()\n"
        "        }\n"
        "        ScarletGuestSceneRegistry.register(controller, dataUUID: dataUUID)\n"
        "        return controller\n",
        "            if !show {\n                vc.terminate()\n":
        "            if !show {\n                ScarletGuestSceneRegistry.unregister(dataUUID)\n                vc.terminate()\n",
        "                .background(.black)\n                .frame(maxWidth: .infinity, maxHeight: .infinity)\n":
        "                .background(.black)\n"
        "                .frame(maxWidth: .infinity, maxHeight: .infinity)\n"
        "                .overlay(alignment: .bottomLeading) {\n"
        "                    if #available(iOS 17.0, *) {\n"
        "                        ScarletGuestSwitcherOverlay(dataUUID: appInfo.dataUUID, displayName: appInfo.displayName)\n"
        "                    }\n"
        "                }\n"
        "                .onDisappear { ScarletGuestSceneRegistry.unregister(appInfo.dataUUID) }\n"
    }
    for before,after in anchors.items():
        if guest_src.count(before)!=1:
            raise RuntimeError(f"Unexpected pinned guest scene layout; anchor count={guest_src.count(before)}: {before!r}")
        guest_src=guest_src.replace(before,after)
    guest_window.write_text(guest_src)

    # The 2026-11-06 on-device crashes (four identical SIGTRAP/BRK #1 in
    # LiveContainerSwiftUI UUID A87CD742-820E-3F50-A48B-481388DCF3B1,
    # PC imageOffset 0x22ACC) identify the pinned dock's force unwrap:
    # keyWindow!.rootViewController!.view.subviews.first!
    # The fresh SwiftUI shell requests MultitaskDockManager.shared before
    # UIWindow has attached its root hierarchy. Preserve the actual dock
    # engine and user windows; defer its attachment until a view exists.
    dock_src_file=engine/"MultitaskSupport/MultitaskDockView.swift"
    assert dock_src_file.is_file(), "Pinned LiveContainer dock source missing"
    dock_source=dock_src_file.read_text()
    unsafe_init="""    override init() {
        super.init()
        keyWindow!.rootViewController!.view.subviews.first!.addSubview(self.windowHostingView)
        setupDockView()
"""
    safe_init="""    // Scarlet: app startup may evaluate the dock before UIKit creates its
    // first key window. Mount the same native host after the scene is ready.
    public func scarletEnsureWindowHost() {
        guard let rootView = keyWindow?.rootViewController?.view else { return }
        let target = rootView.subviews.first(where: { $0 !== windowHostingView }) ?? rootView
        if windowHostingView.superview !== target {
            windowHostingView.removeFromSuperview()
            target.addSubview(windowHostingView)
        }
    }

    @objc private func scarletWindowBecameVisible(_ notification: Notification) {
        DispatchQueue.main.async { [weak self] in
            self?.scarletEnsureWindowHost()
        }
    }

    override init() {
        super.init()
        scarletEnsureWindowHost()
        NotificationCenter.default.addObserver(self,
            selector: #selector(scarletWindowBecameVisible(_:)),
            name: UIWindow.didBecomeVisibleNotification,
            object: nil)
        setupDockView()
"""
    assert dock_source.count(unsafe_init)==1, "Pinned dock startup layout changed"
    dock_source=dock_source.replace(unsafe_init,safe_init)
    assert "keyWindow!.rootViewController!.view.subviews.first!" not in dock_source, "Unsafe force unwrap retained"
    dock_src_file.write_text(dock_source)
    guest_signing=instrument_original_guest_signing(engine)
    guest_manager=hide_embedded_sidestore_guest_navigation(engine)
    native_settings=attach_native_settings_diagnostics(engine)
    native_tweaks_theme=apply_scarlet_native_tweaks_theme(engine)
    nested_diagnostic_layout=attach_jitless_diagnostic_scroll_margins(engine)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    data={
        "schema":1,"newRootCompiled":False,
        "upstreamAppEntryPatched":True,
        "invalidPersistedGuestSkippedWithoutMutation":True,
        "hostBootPhaseLoggingInjected":True,
        "onDeviceSigtrapDockForceUnwrapGuarded":True,
        "dockAttachDeferredToWindowVisibility":True,
        "hostEntry":"ScarletIntegratedHostView",
        "realLCGuestModelsUsed":True,
        "originalGuestImporterPreserved":True,
        "embeddedSideStoreGuestUIEnabled":False,
        "embeddedSideStoreEnginePreserved":True,
        "nativeGuestManager":guest_manager,
        "originalLCGuestSigningDiagnostics":guest_signing,
        "nativeSettingsDiagnostics":native_settings,
        "nativeTweaksTheme":native_tweaks_theme,
        "nativeJITLessDiagnosticScroll":nested_diagnostic_layout,
        "localDiagnosticJournal":True,
        "shareablePrivacyRedactedLog":True,
        "originalNativeUIGlassEffect":True,
        "upstreamLiveContainerSourceUntouched":False,
        "upstreamLiveContainerModifiedTrackedPaths":[
            "LiveContainerSwiftUI/App/LiveContainerSwiftUIApp.swift",
            "MultitaskSupport/MultitaskAppWindow.swift",
            "MultitaskSupport/MultitaskDockView.swift",
            "LiveContainerSwiftUI/Views/AppList/LCAppListView.swift",
            "LiveContainerSwiftUI/Views/Settings/LCSettingsView.swift",
            "LiveContainerSwiftUI/Views/Settings/LCJITLessDiagnoseView.swift",
            "LiveContainerSwiftUI/Views/LCTweaksView.swift",
            "LiveContainerSwiftUI/Models/LCAppModel.swift"
        ],

        "customAppIcon":figma_icon,
        "guestOnlySwitcherSourceInjected":True,
        "guestSnapshotCaptureSourceInjected":True,
        "guestRuntimeCaptureDeviceVerified":False,
        "actualIOSExecutionVerified":False,
        "windowMaximizeAndCloseComplete":False,
        "sources":[dict(path=str(x.relative_to(engine)),sha256=file_sha(x))
                   for x in sorted(out.glob("*.swift"))],
        "entrySHA256":file_sha(entry),
        "note":"Compiles only when real xcodebuild archive succeeds; not proof of install/working Liquid Glass gestures."
    }
    a.report.write_text(json.dumps(data,indent=2)+"\n")
    print("[PASS] Fresh Scarlet host sources injected into file-synchronized Xcode project")
    print("[PASS] Crash-traced dock window force unwrap replaced by deferred, data-preserving mount")
    print("[PASS] Original LC guest IPA/URL import preserved; SideStore guest UI shortcuts removed (engine retained)")
    print("[PASS] Full-size native Settings and private on-device diagnostics/sharing injected")
    print("[PASS] New Figma Scarlet icon compiled into AppIcon.appiconset source; Xcode archive pending")
    print("[BLOCK] Await actual Xcode archive and iPhone runtime validation")
if __name__=="__main__":main()
