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
    bridge = engine / "LiveContainerSwiftUI/LiveContainerSwiftUI-Bridging-Header.h"
    assert bridge.is_file(), "Pinned LC Swift bridging header missing"
    bridging = bridge.read_text()
    signature_include = '#include "../LiveContainer/LCMachOUtils.h"'
    assert 'LCMachOUtils.h' not in bridging, "Pinned LC bridge changed"
    bridge.write_text(bridging.replace('#include "LCAppInfo.h"',
        '#include "LCAppInfo.h"\n' + signature_include, 1))
    assert '"signing_started"' not in source and '"signing_reason"' not in source, (
        "LC guest signing diagnostics already injected")
    original = "        try await signApp(force: false)\n"
    assert source.count(original) == 1, "Pinned LC runApp signing step changed"
    source = source.replace(original, """        ScarletDiagnosticRecorder.shared.record("guest", "signing_started")
        do {
            try await signApp(force: false)
            // The pinned LC ObjC signer uses this SAME kernel-level code
            // signature check internally. Read back the executable again
            // after the async completion, not merely the callback status.
            if #available(iOS 26.0, *), !appInfo.dontSign, !appInfo.is32bit {
                guard let bundlePath = appInfo.bundlePath(),
                      let executable = Bundle(path: bundlePath)?.executableURL else {
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "signature_readback_failed",
                        status: "error", fields: ["reason": "executable_missing"])
                    throw "lc.signer.latestCertificateInvalidErr".loc
                }
                let valid = executable.path.withCString { checkCodeSignature($0) }
                guard valid else {
                    ScarletDiagnosticRecorder.shared.record(
                        "guest", "signature_readback_failed",
                        status: "error", fields: ["reason": "code_signature_invalid"])
                    throw "lc.signer.latestCertificateInvalidErr".loc
                }
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "signature_readback_verified",
                    status: "success",
                    fields: ["result": "kernel_code_signature_check_passed"])
            } else {
                ScarletDiagnosticRecorder.shared.record(
                    "guest", "signature_readback_skipped",
                    fields: ["reason": appInfo.dontSign ? "signing_disabled" : "jit_required"])
            }
            ScarletDiagnosticRecorder.shared.record(
                "guest", "signing_call_returned",
                fields: ["result": "original_signing_call_completed"])
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
        # Upstream installIpaFile contains nonthrowing early exits. Without
        # defer, its spinner can stay active forever and disable "Close".
        '        defer { installprogressVisible = false }\n'
        '        ScarletDiagnosticRecorder.shared.record("guest_import", "file_import_requested")\n',
        "            try await installIpaFile(fileUrl)\n":
        '            try await installIpaFile(fileUrl)\n'
        '            ScarletDiagnosticRecorder.shared.record("guest_import", "import_pipeline_completed",\n'
        '                status: scarletGuestImportSignFailed ? "warning" : "info",\n'
        '                fields: ["result": scarletGuestImportSignFailed\n'
        '                         ? "import_only_signing_unverified" : "launch_unverified"])\n',
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
    # The pinned upstream importer may return with signSuccess=false and
    # signError=nil. Never label that case as an actually usable guest.
    guard_after_sign = "        if let appToReplace {\n            // copy previous configration to new app\n"
    # Synthetic manager fixtures omit the real sign/replace loop.
    if guard_after_sign in source:
        assert source.count(guard_after_sign) == 1, "Pinned sign result boundary changed"
        source = source.replace(guard_after_sign, """        if !signSuccess {
            scarletGuestImportSignFailed = true
            if signError == nil {
                ScarletDiagnosticRecorder.shared.record(
                    "guest_import", "import_signing_unverified",
                    status: "warning",
                    fields: ["reason": "signer_returned_false_without_error"])
            }
        }
        if #available(iOS 26.0, *),
           (LCUtils.certificateData() == nil ||
            LCSharedUtils.certificatePassword() == nil) {
            scarletGuestImportSignFailed = true
            ScarletDiagnosticRecorder.shared.record(
                "guest_import", "import_signing_unverified",
                status: "warning",
                fields: ["reason": "jitless_certificate_missing"])
        }
""" + guard_after_sign, 1)
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
    private let scarletActivity: ScarletGuestImportActivity?
    @State private var scarletDidStartQueuedImport = false
    @State private var scarletQueuedImportFinished = false
    @State private var scarletGuestImportSignFailed = false

    init(scarletQueuedIPAURL: URL? = nil,
         scarletActivity: ScarletGuestImportActivity? = nil,
         scarletOnImportFinished: (() -> Void)? = nil) {
        self.scarletQueuedIPAURL = scarletQueuedIPAURL
        self.scarletActivity = scarletActivity
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
                scarletQueuedInstallView(queuedIPA)
            } else {
                ScrollView {
"""
    # The original LC app manager body is a large SwiftUI ViewBuilder.
    # Keeping this complex branded install UI inline inside NavigationView
    # caused Xcode 27.2 to time out type checking at LCAppListView.swift:270.
    # Move it into a dedicated helper, isolating the result builder.
    progress_view = """    @ViewBuilder
    private func scarletQueuedInstallView(_ queuedIPA: URL) -> some View {
                VStack(spacing: 20) {
                    if #available(iOS 26.0, *) {
                        Image(systemName: scarletGuestImportSignFailed
                              ? "exclamationmark.shield.fill"
                              : "shippingbox.fill")
                            .font(.system(size: 29, weight: .medium))
                            .foregroundStyle(Color(red: 0.76, green: 0.67, blue: 1))
                            .frame(width: 62, height: 62)
                            .glassEffect()
                    } else {
                        Image(systemName: scarletGuestImportSignFailed
                              ? "exclamationmark.shield.fill"
                              : "shippingbox.fill")
                            .font(.system(size: 29, weight: .medium))
                            .foregroundStyle(Color(red: 0.76, green: 0.67, blue: 1))
                            .frame(width: 62, height: 62)
                            .background(.ultraThinMaterial,
                                        in: RoundedRectangle(cornerRadius: 18))
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
                    if !scarletQueuedImportFinished {
                        ProgressView(value: Double(installProgressPercentage), total: 1.0)
                            .tint(Color(red: 0.76, green: 0.67, blue: 1))
                            .accessibilityIdentifier("SCARLET_GUEST_IMPORT_ACTUAL_PROGRESS")
                    } else if scarletGuestImportSignFailed {
                        Label("서명 인증서 확인 필요", systemImage: "exclamationmark.shield")
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(Color.orange)
                    } else {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(Color(red: 0.76, green: 0.67, blue: 1))
                            .accessibilityLabel("가져오기 완료")
                    }
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
                // The parent .sheet has the only rounded surface.
                // Do not draw a second rounded card, border, or black scrim
                // inside the native LiveContainer importer.
                .padding(.horizontal, 26)
                .padding(.vertical, 16)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(Color.clear)
                .onChange(of: installProgressPercentage) { value in
                    scarletActivity?.update(Double(value))
                }
                .onAppear {
                    guard !scarletDidStartQueuedImport else { return }
                    scarletDidStartQueuedImport = true
                    if !didAppear { onAppear() }
                    Task { @MainActor in
                        await startInstallApp(queuedIPA)
                        // This SwiftUI worker is hosted independently from
                        // the progress sheet. Completion is not launch success.
                        scarletQueuedImportFinished = true
                        scarletActivity?.finish(
                            signingUnverified: scarletGuestImportSignFailed,
                            failed: errorShow)
                        scarletOnImportFinished?()
                    }
                }
                .accessibilityIdentifier("SCARLET_GUEST_IMPORT_PROGRESS_ONLY")
                .accessibilityIdentifier("SCARLET_BRANDED_GUEST_IMPORT_CARD")
    }

"""
    assert source.count(begin) == 1, "Pinned LC app manager body changed"
    source = source.replace(begin, replacement)
    body_anchor = "    var body: some View {" + chr(10)
    assert source.count(body_anchor) == 1, "Pinned LC body changed"
    source = source.replace(body_anchor, progress_view + body_anchor, 1)
    end = """        }
        .navigationViewStyle(StackNavigationViewStyle())
"""
    assert source.count(end) == 1, "Pinned LC NavigationView close changed"
    source = source.replace(end, """            }
        }
        .navigationViewStyle(StackNavigationViewStyle())
""")

    # Search belongs to upstream app list ONLY; never render its floating
    # search bar across the queued guest installation progress sheet.
    original_search = "        .searchable(text: $searchContext.query)\n"
    original_scroll = "            .navigationBarProgressBar(show:$installprogressVisible, progress: $installProgressPercentage)\n"
    if original_search in source:
        assert source.count(original_search) == 1, "Pinned upstream searchable moved"
        assert source.count(original_scroll) == 1, "Pinned upstream progress scroll moved"
        source = source.replace(original_search, "", 1)
        source = source.replace(original_scroll,
            "            .searchable(text: $searchContext.query)\n" + original_scroll, 1)

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
        '    @State private var scarletShowAccountAdditionNotice = false\n'
        '    @State private var scarletLoginVerified: Bool? = nil\n'
        '    @State private var scarletSigningCertAvailable = false\n')
    new_section="""        NavigationView {
            Form {
                Section {
                    if scarletLoginVerified == true {
                        Label("로그인됨", systemImage: "checkmark.seal.fill")
                            .foregroundStyle(.green)
                            .accessibilityIdentifier("SCARLET_SETTINGS_LOGIN_VERIFIED")
                        Button {
                            ScarletDiagnosticRecorder.shared.record("auth", "add_account_requested")
                            scarletShowAccountAdditionNotice = true
                        } label: {
                            Label("추가 로그인", systemImage: "person.badge.plus")
                        }
                        .accessibilityIdentifier("SCARLET_SETTINGS_ADD_LOGIN")
                    } else if scarletLoginVerified == nil {
                        Label("로그인 상태 확인 중", systemImage: "clock")
                            .foregroundStyle(.secondary)
                    } else {
                        Button {
                            ScarletDiagnosticRecorder.shared.record("auth", "open_from_settings")
                            scarletShowAppleLogin = true
                        } label: {
                            Label("로그인", systemImage: "person.crop.circle")
                        }
                        .accessibilityIdentifier("SCARLET_SETTINGS_NATIVE_APPLE_LOGIN")
                    }
                    Text(scarletSigningCertAvailable ? "서명 준비됨" : "서명 확인 필요")
                        .font(.footnote)
                        .foregroundStyle(scarletSigningCertAvailable ? Color.green : Color.secondary)
                        .accessibilityIdentifier("SCARLET_CERTIFICATE_SEPARATE_FROM_LOGIN")
                    if #available(iOS 16.0, *) {
                        NavigationLink {
                            ScarletDiagnosticLogView()
                        } label: {
                            Label("진단 로그 보기 및 공유", systemImage: "ladybug")
                        }
                        .accessibilityIdentifier("SCARLET_NATIVE_DIAGNOSTICS_ENTRY")
                    }
                } header: {
                    Text("계정")
                }
"""
    # Surface the *actual* signed runtime entitlements and original SideStore
    # refresh entry inside the existing LC settings Form, never a second UI.
    extension_anchor='''                } header: {
                    Text("계정")
                }
'''
    assert new_section.count(extension_anchor) == 1, "Scarlet settings section moved"
    # V7: put one certificate/JIT-Less control card in the native
    # JIT-Less slot, not a second independent settings section.
    source=source.replace(form_anchor,new_section)
    jitless_begin = '                if sharedModel.multiLCStatus != 2 {\n                    Section{'
    jitless_after = '                if (store != .Unknown && store != .ADP) || LCUtils.isAppGroupAltStoreLike() {'
    # Small, synthetic 15-section test fixture has no real JIT-Less block;
    # retain its pre-existing one-section injection contract.
    if jitless_begin not in source or jitless_after not in source:
        assert source.count(extension_anchor)==1
        source=source.replace(extension_anchor, extension_anchor+
            '                if #available(iOS 17.0, *) {\n'
            '                    ScarletSigningReadinessPanel()\n'
            '                }\n')
    else:
        i=source.index(jitless_begin)
        j=source.index(jitless_after,i)
        original_jit=source[i:j]
        assert 'importCertificateFromSideStore()' in original_jit
        assert 'removeCertificate()' in original_jit
        assert 'LCJITLessDiagnoseView()' in original_jit
        source=(source[:i] +
            '                if #available(iOS 17.0, *) {\n'
            '                    ScarletSigningReadinessPanel()\n'
            '                    ScarletFeatureModulesSection()\n'
            '                } else {\n' + original_jit +
            '                }\n' + source[j:])
        extra_jit="""                        if(sharedModel.multiLCStatus == 2) {
                            NavigationLink {
                                LCJITLessDiagnoseView()
                            } label: {
                                Text("lc.settings.jitlessDiagnose".loc)
                            }
                        }"""
        assert source.count(extra_jit)==1
        source=source.replace(extra_jit,"""                        if #available(iOS 17.0, *) {
                            // JIT-Less is now in one combined certificate section.
                        } else if sharedModel.multiLCStatus == 2 {
                            NavigationLink {
                                LCJITLessDiagnoseView()
                            } label: {
                                Text("lc.settings.jitlessDiagnose".loc)
                            }
                        }""")
    # Preserve upstream localized certificate alerts verbatim.
    # Supplemental verification status is shown by Scarlet separately.
    source=source.replace(style_anchor,style_anchor+
        '        .alert("추가 로그인", isPresented: $scarletShowAccountAdditionNotice) {\n'
        '            Button("확인", role: .cancel) { }\n'
        '        } message: {\n'
        '            Text("현재 연결된 SideStore 인증 엔진은 단일 활성 계정만 유지합니다. 이 상태에서 다른 Apple ID로 로그인하면 기존 계정이 교체될 수 있어 자동 추가를 제한합니다. 다중 계정은 계정별 보안 저장소와 서명 팀 전환을 연결해야 합니다.")\n'
        '        }\n'
        '        .sheet(isPresented: $scarletShowAppleLogin, onDismiss: {\n'
        '            Task { @MainActor in\n'
        '                if #available(iOS 17.0, *) {\n'
        '                    scarletLoginVerified = await ScarletConnectedSideSignEngine().storedAuthenticated()\n'        '                    scarletSigningCertAvailable = LCUtils.certificateData() != nil &&\n'
        '                        LCSharedUtils.certificatePassword() != nil\n'
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
        '                    scarletLoginVerified = await ScarletConnectedSideSignEngine().storedAuthenticated()\n'        '                    scarletSigningCertAvailable = LCUtils.certificateData() != nil &&\n'
        '                        LCSharedUtils.certificatePassword() != nil\n'
        '                }\n'
        '            }\n'
        '        }\n'
        '        .onReceive(NotificationCenter.default.publisher(\n'
        '            for: Notification.Name("ScarletGuestAuthVerified"))) { _ in\n'
        '            Task { @MainActor in\n'
        '                if #available(iOS 17.0, *) {\n'
        '                    scarletLoginVerified = await ScarletConnectedSideSignEngine().storedAuthenticated()\n'        '                    scarletSigningCertAvailable = LCUtils.certificateData() != nil &&\n'
        '                        LCSharedUtils.certificatePassword() != nil\n'
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
        '            .scarletSettingsPurplePalette()\n'
        '            .scarletSettingsScrollLimit()\n'
        '            .navigationBarTitle("lc.tabView.settings".loc)\n')
    # The original LC settings action only searches the legacy Keychain
    # service. Pinned SideStore uses com.SideStore.SideStore. Add a guarded
    # same-team read before the untouched original fallback; keep its label.
    import_method = "    func importCertificateFromSideStore() async {\n"
    if import_method in source:
        assert source.count(import_method) == 1
        helper = """    private func scarletReadSideStoreCertForCurrentTeam() -> (Data, String)? {
        for service in ["com.SideStore.SideStore", "com.kdt.livecontainer"] {
            let q: [String: Any] = [
                kSecClass as String: kSecClassGenericPassword,
                kSecAttrAccount as String: "signingCertificate",
                kSecReturnData as String: true,
                kSecMatchLimit as String: kSecMatchLimitOne,
                kSecAttrService as String: service,
                kSecAttrSynchronizable as String: kSecAttrSynchronizableAny
            ]
            var value: CFTypeRef?
            guard SecItemCopyMatching(q as CFDictionary, &value) == errSecSuccess,
                  let data = value as? Data, !data.isEmpty else { continue }
            var passwordQuery = q
            passwordQuery[kSecAttrAccount as String] = "signingCertificatePassword"
            var pwd: CFTypeRef?
            let passwordStatus = SecItemCopyMatching(passwordQuery as CFDictionary, &pwd)
            guard passwordStatus == errSecSuccess ||
                  passwordStatus == errSecItemNotFound else { continue }
            let password = (pwd as? Data)
                .flatMap { String(data: $0, encoding: .utf8) } ?? ""
            guard let certificateTeam = LCUtils.getCertTeamId(
                withKeyData: data, password: password),
                  let hostTeam = LCSharedUtils.teamIdentifier(),
                  certificateTeam == hostTeam else { continue }
            return (data, password)
        }
        return nil
    }

"""
        source = source.replace(import_method, helper + import_method, 1)
        confirmation = "            if let ans = await certificateImportFromBuiltInSideStoreAlert.open(), ans {\n"
        assert source.count(confirmation) == 1, "Pinned LC certificate confirmation changed"
        source = source.replace(confirmation, confirmation + """                if let (certData, password) = scarletReadSideStoreCertForCurrentTeam() {
                    onSideStoreCertificateCallback(certificateData: certData, password: password)
                    if LCUtils.certificateData() == certData &&
                       LCSharedUtils.certificatePassword() == password {
                        ScarletDiagnosticRecorder.shared.record(
                            "guest", "certificate_bridge_imported",
                            status: "success", fields: ["reason": "manual_same_team_readback"])
                    }
                    return
                }
""", 1)
    source, styled_rows = theme_native_settings_section_rows(source)
    # Remove obsolete upstream multitasking SETTINGS menu; engine stays.
    multitask_menu = """                if #available(iOS 16.1, *) {
                    Section {
                        NavigationLink {
                            LCMultitaskSettingView()
                        } label: {
                            Text("lc.appBanner.multitask".loc)
                        }
                    } footer: {
                        Text("lc.settings.multitaskDesc".loc)
                    }
                    .listRowBackground(Color(red: 36.0/255, green: 35.0/255, blue: 58.0/255).opacity(0.80))
                }
"""
    if multitask_menu in source:
        assert source.count(multitask_menu) == 1
        source = source.replace(multitask_menu, "")
    elif "LCMultitaskSettingView()" in source:
        raise RuntimeError("Upstream multitask menu changed; refuse unsafe removal")
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


def remove_upstream_legacy_window_ui(engine: Path) -> dict:
    """Physically remove old LC side-dock SwiftUI + three-button chrome.

    The original LiveContainer signing/import/guest storage engines stay
    pinned. A tiny nonvisual API registry replaces the 1200-line dock source
    so upstream callers still compile without UI rendering side effects.
    """
    dock = engine/"MultitaskSupport/MultitaskDockView.swift"
    decorated = engine/"MultitaskSupport/DecoratedAppSceneViewController.m"
    assert dock.is_file() and decorated.is_file(), "Pinned LC visual sources missing"
    original_dock=dock.read_text()
    assert "public struct MultitaskDockSwiftView: View" in original_dock
    assert "struct CollapsedDockView: View" in original_dock
    assert "class MultitaskDockManager" in original_dock
    dock.write_text(LEGACY_DOCK_RENDERER_REMOVED_SOURCE)
    assert "MultitaskDockSwiftView" not in dock.read_text()
    assert "CollapsedDockView" not in dock.read_text()

    source=decorated.read_text()
    start=source.index("    NSArray *menuItems = @[",source.index("- (instancetype)initWindowName:"))
    end=source.index("    return self;\n}", start)
    # Delete all original colored close/maximize/minimize controls, window
    # title menu and slider menu; not just hidden at runtime.
    source=source[:start]+source[end:]
    start=source.index("- (void)setupDecoratedView {")
    end=source.index("// Stolen from UIKitester", start)
    # The legacy 320x480 scaled scene and its 44pt fake title strip are gone.
    # The compatibility scene occupies its original unscaled superview; this
    # is not a V34 virtual/maximized content rectangle.
    replacement="""- (void)setupDecoratedView {
    self.view.frame = self.view.superview.bounds;
    self.view.autoresizingMask =
        UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.view.backgroundColor = UIColor.clearColor;
    self.view.layer.cornerRadius = 0;
    self.view.layer.masksToBounds = NO;
    self.contentView = self.view;
    [self addChildViewController:_appSceneVC];
    [self.view addSubview:_appSceneVC.view];
    _appSceneVC.view.frame = self.view.bounds;
    _appSceneVC.view.autoresizingMask =
        UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [_appSceneVC didMoveToParentViewController:self];
}

"""
    source=source[:start]+replacement+source[end:]
    # Strip the virtual-window layout manipulations too, so even an
    # unexpected native caller cannot create the old 44pt content offset.
    start=source.index("- (void)updateVerticalConstraints {")
    end=source.index("- (UIEdgeInsets)updateMaximizedSafeAreaWithSettings:",start)
    source=source[:start]+"""- (void)updateVerticalConstraints {
    self.appSceneVC.view.frame = self.view.bounds;
}

"""+source[end:]
    # Remove the old custom frame/view-scale resizing methods while preserving
    # selectors required by the original Objective-C runtime.
    assert 'UIBarButtonItem *minimizeButton' not in source
    assert 'UINavigationBar *navigationBar = ' not in source
    assert 'CGRectMake(0, 0, isLandscape ? 480 : 320' not in source
    decorated.write_text(source)
    return {
        "originalDockSourceLines": len(original_dock.splitlines()),
        "replacementNonvisualLines": len(LEGACY_DOCK_RENDERER_REMOVED_SOURCE.splitlines()),
        "chromeMinMaxCloseRemoved": True,
        "legacyScene320x480GeometryRemoved": True,
    }

LEGACY_DOCK_RENDERER_REMOVED_SOURCE = r"""// Scarlet V36: source-level removal of the legacy LiveContainer side dock.
// No SwiftUI dock views, no window UI, no UIApplication window attachment.
// The object is a nonvisual compatibility registry for pinned LC call sites.
import Foundation
import UIKit
import SwiftUI
import Combine

@objc class DockAppModel: NSObject, ObservableObject, Identifiable {
    let id = UUID()
    @objc let appName: String
    @objc let appUUID: String
    let appInfo: LCAppInfo?
    let view: UIView?

    @objc init(appName: String, appUUID: String, appInfo: LCAppInfo? = nil,
               view: UIView?) {
        self.appName = appName
        self.appUUID = appUUID
        self.appInfo = appInfo
        self.view = view
        super.init()
    }
}

@available(iOS 16.0, *)
@objc public class MultitaskDockManager: NSObject, ObservableObject {
    @objc public static let shared = MultitaskDockManager()
    @Published var apps: [DockAppModel] = []
    @objc public var isCollapsed: Bool = false
    @objc public var windowHostingView = VirtualWindowsHostView()

    @objc public func addRunningApp(_ appName: String, appUUID: String,
                                    view: UIView?) {
        guard !apps.contains(where: { $0.appUUID == appUUID }) else { return }
        apps.append(DockAppModel(appName: appName, appUUID: appUUID,
                                 view: view))
    }

    @objc public func removeRunningApp(_ appUUID: String) {
        apps.removeAll(where: { $0.appUUID == appUUID })
    }

    // Upstream guest manager calls this API to *find* an already owned
    // window. It never constructs a decorated/scaled window or side rail.
    public func bringMultitaskViewToFront(uuid: String,
                                          from center: CGPoint? = nil) -> Bool {
        if #available(iOS 16.1, *) {
            return MultitaskWindowManager.openExistingAppWindow(dataUUID: uuid)
        }
        return false
    }

    @objc public func minimizeAllWindows(except: DecoratedAppSceneViewController? = nil) {
        for app in apps {
            if let decorated = app.view?._viewDelegate()
                as? DecoratedAppSceneViewController, decorated !== except {
                decorated.minimizeWindow()
            }
        }
    }
}
"""

def add_v45_fullscreen_scene_slot(engine: Path) -> dict:
    """Create a single full-screen remote-scene viewport, never a fake LC window.

    Only Scarlet-tagged AppSceneViewController instances use this non-scaling
    geometry path; all pinned normal LC scene behavior remains unchanged.
    """
    header = engine/"MultitaskSupport/AppSceneViewController.h"
    h = header.read_text()
    old = "@property(nonatomic) CGFloat scaleRatio;\n"
    assert h.count(old) == 1, "V45 upstream AppScene header changed"
    h = h.replace(old, old +
        "@property(nonatomic) BOOL scarletNativeFullscreenSlot;\n"
        "@property(nonatomic) BOOL scarletNativeTransparentChromeSlot;\n"
        "- (void)scarletApplyNativeTransparentChromeSlot:(BOOL)enabled;\n"
        "- (nullable NSNumber *)scarletApplyHostingContentSafeArea:(UIEdgeInsets)desired;\n"
        "- (BOOL)scarletRemoteContentReady;\n"
        "- (BOOL)scarletEnsureRemoteForeground;\n", 1)
    header.write_text(h)
    protocol_header = engine/"MultitaskSupport/AppSceneViewController.h"
    protocol_src = protocol_header.read_text()
    marker = '- (void)appSceneVCWillActivateScene:(AppSceneViewController *)vc;'
    assert protocol_src.count(marker) == 1
    protocol_src = protocol_src.replace(marker, marker +
        '\n- (void)appSceneVCDidAttachRemoteContent:(AppSceneViewController *)vc;', 1)
    protocol_header.write_text(protocol_src)
    target = engine/"MultitaskSupport/AppSceneViewController.m"
    a = target.read_text()
    # V48-R4: iOS 27 uses _UISceneHostingController. The V48 delegate
    # updates only a temporary settings COPY and its FBScene remote guest
    # still receives zero safe insets while statusBarDisabled is YES.
    # This patch is limited to scarletNativeFullscreenSlot. The original LC
    # scene path remains untouched, including classic guest launch geometry.
    assert a.count("        settings.statusBarDisabled = !self.isNativeWindow;") == 1
    a = a.replace("        settings.statusBarDisabled = !self.isNativeWindow;",
                  "        settings.statusBarDisabled = !self.isNativeWindow && !self.scarletNativeFullscreenSlot;", 1)
    # Pilot-only, host-process geometry authority. No guest-app UIKit swizzle
    # and no extra window/presentation layer. Per FBScene instance cache keeps
    # the last validated portrait geometry across inactive UIKit transitions.
    authority_header = r"""#pragma once
#import <UIKit/UIKit.h>
#import <objc/runtime.h>
#import <math.h>

// Each distinct FBScene owns its own last valid portrait insets. A global
// singleton would mix guest A and B and reproduce the old misalignment.
static inline const void *SCGeometryCacheKey(void) {
    return (const void *)sel_registerName("Scarlet.SceneGeometry.Authority.V1");
}
static inline const void *SCGeometryReportKey(void) {
    return (const void *)sel_registerName("Scarlet.SceneGeometry.LastPublished.V1");
}
static inline UIEdgeInsets SCGeometryResolve(id remoteScene, UIEdgeInsets measured,
                                            UIInterfaceOrientation orientation,
                                            BOOL *didRecover) {
    if(didRecover) *didRecover = NO;
    if(!remoteScene) return measured;
    // Never reuse portrait Dynamic Island geometry after rotation.
    if(!UIInterfaceOrientationIsPortrait(orientation)) return measured;
    NSValue *saved = objc_getAssociatedObject(remoteScene, SCGeometryCacheKey());
    UIEdgeInsets previous = saved ? saved.UIEdgeInsetsValue : UIEdgeInsetsZero;
    BOOL valid = isfinite(measured.top) && measured.top >= 18 && measured.top <= 160;
    if(valid) {
        if(!saved || fabs(previous.top-measured.top) > 0.5 ||
           fabs(previous.bottom-measured.bottom) > 0.5) {
            objc_setAssociatedObject(remoteScene, SCGeometryCacheKey(),
                [NSValue valueWithUIEdgeInsets:measured], OBJC_ASSOCIATION_RETAIN_NONATOMIC);
        }
        return measured;
    }
    // iOS sometimes temporarily detaches the host window at deactivation.
    // A zero from that transient state must NOT erase a known 62pt island.
    if(saved && previous.top >= 18 && previous.top <= 160 &&
       isfinite(measured.top) && measured.top >= 0 && measured.top < 18) {
        measured.top = previous.top;
        if(measured.bottom <= 0 && previous.bottom >= 0)
            measured.bottom = previous.bottom;
        if(didRecover) *didRecover = YES;
    }
    return measured;
}
// Reduce tens of identical FBScene update notifications to one state change.
static inline BOOL SCGeometryShouldReport(id scene, UIEdgeInsets insets,
                                           BOOL recovered) {
    if(!scene) return NO;
    NSString *now = [NSString stringWithFormat:@"%.0f:%.0f:%d",
                           insets.top, insets.bottom, (int)recovered];
    NSString *previous = objc_getAssociatedObject(scene, SCGeometryReportKey());
    if([now isEqualToString:previous]) return NO;
    objc_setAssociatedObject(scene, SCGeometryReportKey(),
                             now, OBJC_ASSOCIATION_COPY_NONATOMIC);
    return YES;
}
"""
    (engine/"MultitaskSupport/ScarletSceneGeometryAuthority.h").write_text(authority_header)
    assert a.count('#import "UIKitPrivate+MultitaskSupport.h"') == 1
    a = a.replace('#import "UIKitPrivate+MultitaskSupport.h"',
                  '#import "UIKitPrivate+MultitaskSupport.h"\n#import <objc/runtime.h>\n'
                  '#import "ScarletSceneGeometryAuthority.h"', 1)
    # Both initialization and later FBScene settings mutations use actual
    # normal-level host UIWindow or the public statusBarManager dimensions.
    helper = r"""
static UIEdgeInsets ScarletPilotHostInsets(UIWindowScene *scene,
                                           UIEdgeInsets fallback) {
    UIWindowScene *hostScene = scene;
    if(!hostScene) {
        for(UIScene *item in UIApplication.sharedApplication.connectedScenes) {
            if([item isKindOfClass:UIWindowScene.class] &&
               item.activationState == UISceneActivationStateForegroundActive) {
                hostScene = (UIWindowScene *)item;
                break;
            }
        }
    }
    if(!hostScene) { return fallback; }
    UIEdgeInsets insets = fallback;
    for(UIWindow *window in hostScene.windows) {
        if(window.windowLevel == UIWindowLevelNormal && !window.isHidden) {
            insets = window.safeAreaInsets;
            break;
        }
    }
    if(insets.top < 1) {
        // Do not hardcode Dynamic Island height (models and orientation vary).
        // A full-bleed SwiftUI host can report 0 even on iPhone island devices.
        CGFloat realStatusBottom = CGRectGetMaxY(hostScene.statusBarManager.statusBarFrame);
        insets.top = MAX(insets.top, realStatusBottom);
    }
    return insets;
}
"""
    old = '@interface AppSceneViewController()\n'
    assert a.count(old) == 2
    a = a.replace(old, helper + '\n' + old, 1)
    old = '''        if(!self.usesHostingControllerAPI) {
            settings.safeAreaInsetsPortrait = self.view.safeAreaInsets;
        }'''
    assert a.count(old) == 1
    a = a.replace(old, '''        if(self.scarletNativeFullscreenSlot) {
            UIEdgeInsets safe = ScarletPilotHostInsets(
                self.view.window.windowScene, self.view.safeAreaInsets);
            // Initial settings can be populated before a scene exists;
            // remote FBScene authority validates and caches at attachment.
            // V48-R6: the resident guest scene fills the host window, so it
            // has no periphery of its own. Express Dynamic Island and home
            // indicator only through the safe area; a nonzero periphery here
            // re-applies the island inset to an already full-bleed frame.
            settings.peripheryInsets = UIEdgeInsetsZero;
            if(self.scarletNativeTransparentChromeSlot) safe.top = 0;
            settings.safeAreaInsetsPortrait = safe;
            if(@available(iOS 19.0, *)) {
                settings.safeAreaEdgeInsets = safe;
            }
            [NSNotificationCenter.defaultCenter postNotificationName:
                @"ScarletPilotRemoteSafeAreaChanged" object:nil
                userInfo:@{@"stage": @"initial_configuration",
                           @"top": @(safe.top), @"bottom": @(safe.bottom)}];
        } else if(!self.usesHostingControllerAPI) {
            settings.safeAreaInsetsPortrait = self.view.safeAreaInsets;
        }''', 1)
    old = '''        FBScene *scene = self.presenter.scene;
        [scene configureParameters:^(FBSMutableSceneParameters *parameters) {'''
    assert a.count(old) == 1
    a = a.replace(old, '''        FBScene *scene = self.presenter.scene;
        if(self.scarletNativeFullscreenSlot) {
            // Associated only with this remote guest scene; other guests and
            // classic LiveContainer never share a geometry authority.
            objc_setAssociatedObject(scene,
                (const void *)sel_registerName("scarletNativeFullscreenSlot"),
                @YES, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
            objc_setAssociatedObject(scene,
                (const void *)sel_registerName("scarletNativeTransparentChromeSlot"),
                @(self.scarletNativeTransparentChromeSlot),
                OBJC_ASSOCIATION_RETAIN_NONATOMIC);
            UIEdgeInsets first = ScarletPilotHostInsets(
                self.view.window.windowScene, self.view.safeAreaInsets);
            BOOL recovered = NO;
            (void)SCGeometryResolve(scene, first, UIInterfaceOrientationPortrait,
                                   &recovered);
        }
        [scene configureParameters:^(FBSMutableSceneParameters *parameters) {''', 1)
    # iOS27 remote display is actually owned by the nested UIKit
    # _UISceneHostingController.sceneViewController. The old outer VC's
    # additionalSafeAreaInsets does not necessarily reach that owner.
    helper = r"""
// Read-only on the UIKit hosting owner. Geometry writes belong to the
// per-FBScene authority, not multiple ancestor additionalSafeAreaInsets.
- (void)scarletApplyNativeTransparentChromeSlot:(BOOL)enabled {
    self.scarletNativeTransparentChromeSlot = enabled;
    FBScene *remote = self.presenter.scene;
    if(remote) {
        objc_setAssociatedObject(remote,
            (const void *)sel_registerName("scarletNativeTransparentChromeSlot"),
            @(enabled), OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    }
}
- (NSNumber *)scarletApplyHostingContentSafeArea:(UIEdgeInsets)desired {
    if(!self.scarletNativeFullscreenSlot || !self.hostingController)
        return nil;
    UIViewController *owner = self.hostingController.sceneViewController;
    if(!owner || !owner.isViewLoaded) return nil;
    return @(owner.view.safeAreaInsets.top);
}
"""
    helper += r"""
// Pilot-only two-phase native render handshake. PID is not proof that the
// remote FBScene hosting view exists. Nothing is injected in the guest.
- (BOOL)scarletRemoteContentReady {
    if(!self.scarletNativeFullscreenSlot || !self.isAppRunning ||
       !self.hostingController || !self.presenter || !self.presenter.scene ||
       !self.contentView || self.contentView.superview != self.view ||
       !self.view.window || CGRectGetWidth(self.contentView.bounds) < 2 ||
       CGRectGetHeight(self.contentView.bounds) < 2)
        return NO;
    return self.hostingController.sceneViewController.view == self.contentView;
}
- (BOOL)scarletEnsureRemoteForeground {
    if(![self scarletRemoteContentReady]) return NO;
    // Clang does not permit casting a @selector expression to void*.
    // Use a stable associated-object key unique to this method.
    static char kFirstForeground;
    if([objc_getAssociatedObject(self,&kFirstForeground) boolValue]) return YES;
    objc_setAssociatedObject(self,&kFirstForeground,@YES,OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    // LiveContainer already has the equivalent update path in
    // setBackgroundNotificationEnabled. Issue it only once after content is
    // attached to prevent inactive->foreground spam and process restarts.
    [self.presenter.scene updateSettingsWithBlock:^(UIMutableApplicationSceneSettings *settings) {
        settings.foreground = YES;
        settings.deactivationReasons = 0;
    }];
    return YES;
}
"""
    anchor = "- (void)setUpAppPresenter {"
    assert a.count(anchor) == 1
    a = a.replace(anchor, helper + "\n" + anchor, 1)
    # Wait until original LC code attaches the actual remote content view;
    # this callback is later than beginExtensionRequestWithInputItems PID.
    needle_content = '    [self.view addSubview:_contentView];'
    assert a.count(needle_content) == 1
    a = a.replace(needle_content, needle_content + r"""
    if(self.scarletNativeFullscreenSlot &&
       [self.delegate respondsToSelector:@selector(appSceneVCDidAttachRemoteContent:)]) {
        __weak typeof(self) weakSelf = self;
        dispatch_async(dispatch_get_main_queue(), ^{
            if(weakSelf && weakSelf.scarletNativeFullscreenSlot)
                [weakSelf.delegate appSceneVCDidAttachRemoteContent:weakSelf];
        });
    }
""",1)
    target.write_text(a)

    hook_file = engine / "MultitaskSupport/UIKitHooks.m"
    hooks = hook_file.read_text()
    assert hooks.count('#import "UIKitPrivate+MultitaskSupport.h"') == 1
    hooks = hooks.replace('#import "UIKitPrivate+MultitaskSupport.h"',
        '#import "UIKitPrivate+MultitaskSupport.h"\n'
        '#import "ScarletSceneGeometryAuthority.h"',1)
    old = '''    // We don't wanna mess up system extensions on iOS 26+
    if(LCHasRemoteSheetProviderSelector && self.ui_viewServiceComponent) {'''
    assert hooks.count(old) == 1
    hooks = hooks.replace(old, '''    // Unlike the legacy LC delegate, iOS 27's hosting controller updates
    // FBScene asynchronously. The remote scene's actual safe area must be
    // recomputed here, not only on the temporary copy in updateSettings.
    BOOL scarletPilot = [objc_getAssociatedObject(self,
        (const void *)sel_registerName("scarletNativeFullscreenSlot")) boolValue];
    if(scarletPilot) {
        id safeUpdate = ^(UIMutableApplicationSceneSettings *settings,
                          FBSSceneTransitionContext *context) {
            updateBlock(settings, context);
            UIEdgeInsets safe = UIEdgeInsetsZero;
            UIWindowScene *homeScene = nil;
            for(UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
                if([scene isKindOfClass:UIWindowScene.class] &&
                   scene.activationState == UISceneActivationStateForegroundActive) {
                    homeScene = (UIWindowScene *)scene;
                    break;
                }
            }
            for(UIWindow *window in homeScene.windows) {
                if(window.windowLevel == UIWindowLevelNormal && !window.isHidden) {
                    safe = window.safeAreaInsets;
                    break;
                }
            }
            if(safe.top < 1) {
                CGFloat statusBottom = CGRectGetMaxY(homeScene.statusBarManager.statusBarFrame);
                safe.top = MAX(safe.top, statusBottom);
            }
            BOOL recovered = NO;
            safe = SCGeometryResolve(self, safe, settings.interfaceOrientation,
                                     &recovered);
            // Native viewport begins at the host's safe Y, so forwarding
            // that same top inset again would double-shift the guest.
            BOOL chrome = [objc_getAssociatedObject(self,
                (const void *)sel_registerName("scarletNativeTransparentChromeSlot"))
                boolValue];
            if(chrome && UIInterfaceOrientationIsPortrait(settings.interfaceOrientation))
                safe.top = 0;
            // V48-R6: keep the guest scene full-bleed and send Dynamic
            // Island/home-indicator guidance only through the scene's safe
            // area. peripheryInsets=safe double-applied the host inset and
            // could shift guest content back under the island.
            settings.peripheryInsets = UIEdgeInsetsZero;
            settings.safeAreaInsetsPortrait =
                LCUIEdgeInsetsRotateToOrientation(safe, settings.interfaceOrientation);
            if(@available(iOS 19.0, *)) {
                settings.safeAreaEdgeInsets = safe;
            }
            if(SCGeometryShouldReport(self, safe, recovered)) {
                [NSNotificationCenter.defaultCenter postNotificationName:
                    @"ScarletPilotRemoteSafeAreaChanged" object:nil
                    userInfo:@{@"stage": recovered ? @"cached_scene_geometry" : @"live_scene_geometry",
                               @"top": @(safe.top), @"bottom": @(safe.bottom)}];
            }
        };
        [self hook__performUpdateWithoutActivation:safeUpdate];
        return;
    }
    // Do not touch original LC, system, SideStore or other view services.
    if(LCHasRemoteSheetProviderSelector && self.ui_viewServiceComponent) {''', 1)
    hook_file.write_text(hooks)
    old = "            if(UIInterfaceOrientationIsLandscape(settings.interfaceOrientation)) {"
    assert a.count(old) == 1
    a = a.replace(old, "            if(!self.scarletNativeFullscreenSlot && UIInterfaceOrientationIsLandscape(settings.interfaceOrientation)) {",1)
    old = "    if(UIInterfaceOrientationIsLandscape(tempSettings.interfaceOrientation)) {"
    assert a.count(old) == 1
    a = a.replace(old,
        "    if(!self.scarletNativeFullscreenSlot && UIInterfaceOrientationIsLandscape(tempSettings.interfaceOrientation)) {",1)
    target.write_text(a)
    return {"singleViewport": True, "legacyDecoratedWindow": False,
            "guestFrameScale": 1, "optIn": True, "sceneTagOnly": True,
            "pilotRemoteSafeArea": "scene_tagged_initial_and_FBScene_update"}




def add_r6p9_deferred_liveprocess_boot(engine: Path) -> dict:
    """Start resident LiveProcess requests only after owning host window attach.

    LiveContainer's AppSceneViewController constructor calls
    beginExtensionRequestWithInputItems: *before* the caller can addChild,
    mount the remote controller, set scarletNativeFullscreenSlot, or attach
    it to the foreground UIWindowScene. The device log accordingly reports
    hosting owner unavailable (-1) before it becomes 62pt. Unlike earlier
    inset workarounds, defer the request at its source until host ownership
    is established; leave every original LC constructor and frame unchanged.
    """
    header = engine/"MultitaskSupport/AppSceneViewController.h"
    h = header.read_text()
    signature = "- (instancetype)initWithBundleId:(NSString*)bundleId dataUUID:(NSString*)dataUUID delegate:(id<AppSceneViewControllerDelegate>)delegate;\n"
    assert h.count(signature) == 1, "R6P9 pinned AppScene initializer header changed"
    addition = (
        "// Resident-only: the extension must not bootstrap before its hosting window exists.\n"
        "- (instancetype)initWithBundleId:(NSString*)bundleId dataUUID:(NSString*)dataUUID "
        "delegate:(id<AppSceneViewControllerDelegate>)delegate scarletDeferExtensionRequest:(BOOL)defer;\n"
        "- (BOOL)scarletBeginDeferredExtensionIfHosted;\n"
    )
    h = h.replace(signature, signature + addition, 1)
    header.write_text(h)

    file = engine/"MultitaskSupport/AppSceneViewController.m"
    a = file.read_text()
    private_anchor = "@property(nonatomic) UIWindowScene *hostScene;\n"
    assert a.count(private_anchor) == 1, "R6P9 private hostScene slot changed"
    a = a.replace(private_anchor,
        "@property(nonatomic, strong) NSExtensionItem *scarletPendingExtensionItem;\n"
        + private_anchor, 1)
    origin = ("- (instancetype)initWithBundleId:(NSString*)bundleId "
              "dataUUID:(NSString*)dataUUID delegate:(id<AppSceneViewControllerDelegate>)delegate {\n")
    assert a.count(origin) == 1, "R6P9 constructor signature changed"
    replacement = (
        "- (instancetype)initWithBundleId:(NSString*)bundleId "
        "dataUUID:(NSString*)dataUUID delegate:(id<AppSceneViewControllerDelegate>)delegate {\n"
        "    return [self initWithBundleId:bundleId dataUUID:dataUUID "
        "delegate:delegate scarletDeferExtensionRequest:NO];\n"
        "}\n"
        "- (instancetype)initWithBundleId:(NSString*)bundleId "
        "dataUUID:(NSString*)dataUUID delegate:(id<AppSceneViewControllerDelegate>)delegate "
        "scarletDeferExtensionRequest:(BOOL)defer {\n"
    )
    a = a.replace(origin, replacement, 1)
    begin = "    [_extension beginExtensionRequestWithInputItems:@[item] completion:^(NSUUID *identifier) {\n"
    assert a.count(begin) == 1, "R6P9 original NSExtension start changed"
    a = a.replace(begin, """    if(defer) {
        // No XPC launch here: the call site has not yet added this VC to a
        // real UIWindowScene. The NSExtension and request payload are ready.
        self.scarletPendingExtensionItem = item;
    } else {
        [self scarletBeginExtensionWithItem:item];
    }

    return self;
}

// Exact original LC extension completion semantics, simply moved into a
// reusable method. Classic/native LC callers invoke it immediately as before.
- (void)scarletBeginExtensionWithItem:(NSExtensionItem *)item {
    id<AppSceneViewControllerDelegate> delegate = self.delegate;
    [self.extension beginExtensionRequestWithInputItems:@[item] completion:^(NSUUID *identifier) {
""", 1)
    end = "    }];\n    \n    return self;\n}\n\n- (void)setUpAppPresenter {"
    # R6P8 setUpAppPresenter has pilot utility methods preceding it;
    # replace only constructor completion end, not the downstream presenter.
    end = "    }];\n    \n    return self;\n}"
    assert a.count(end) == 1, "R6P9 original completion end changed"
    a = a.replace(end, """    }];
}

// Idempotent resident-only kick-off. Do not request any process until this
// exact controller has an owning host UIWindowScene, thus no provisional
// process/remote scene can observe an unattached UIKit hierarchy.
- (BOOL)scarletBeginDeferredExtensionIfHosted {
    NSExtensionItem *item = self.scarletPendingExtensionItem;
    if(!item || !self.scarletNativeFullscreenSlot ||
       !self.isViewLoaded || !self.view.window ||
       !self.view.window.windowScene || !self.parentViewController)
        return NO;
    self.scarletPendingExtensionItem = nil; // exactly-once, no self-retain cycle
    [self scarletBeginExtensionWithItem:item];
    return YES;
}
""", 1)
    # Important: the source path still retains a single original LC
    # beginExtensionRequestWithInputItems: call in the shared start routine.
    assert a.count("beginExtensionRequestWithInputItems:@[item]") == 1
    assert a.count("scarletDeferExtensionRequest:NO") == 1
    assert a.count("self.scarletPendingExtensionItem = nil;") == 1
    file.write_text(a)
    return {
        "source": str(file.relative_to(engine)),
        "residentLaunchDeferred": True,
        "classicLaunchImmediate": True,
        "extensionStartSites": 1,
        "noStatusBarOrGeometryMutation": True,
    }



def add_r6p11_guest_sdk_contract(engine: Path) -> dict:
    """Resident-only automatic guest Mach-O SDK contract at dyld bootstrap.

    Unlike previously retried Safe Area / FBScene / UIWindow geometry, this
    changes dyld's SDK compatibility query to the *guest executable's own*
    LC_BUILD_VERSION.sdk rather than always inheriting the LiveProcess
    extension executable's SDK. UIKit was already loaded by NSExtensionMain;
    therefore the change is a reversible hypothesis, NOT proven to update
    all already-cached UIKit layout decisions. The experiment is scoped to
    Scarlet's resident-only extension request and never overwrites explicit
    guest spoofSDKVersion settings.
    """
    vc = engine / "MultitaskSupport/AppSceneViewController.m"
    text = vc.read_text()
    existing = "        self.scarletPendingExtensionItem = item;"
    assert text.count(existing) == 1, "R6P11 deferred extension contract not found"
    text = text.replace(existing, """        // R6P11: one anonymous feature bit, never a guest identifier or
        // per-app exception; only resident/native fullscreen sessions opt in.
        NSMutableDictionary *residentInfo = [item.userInfo mutableCopy];
        residentInfo[@"scarletResidentSDKContract"] = @YES;
        item.userInfo = residentInfo;
        self.scarletPendingExtensionItem = item;""", 1)
    vc.write_text(text)

    liveprocess = engine / "LiveProcess/main.m"
    source = liveprocess.read_text()
    requested = "    retrievedAppInfo = [context.inputItems.firstObject userInfo];\n"
    assert source.count(requested) == 1, "R6P11 pinned LiveProcess extension intake changed"
    source = source.replace(requested, requested + """    // Consumed after app selection, before LiveContainerMain guest bootstrap.
    // Classic LiveProcess requests have no flag and retain original SDK.
    [NSUserDefaults.standardUserDefaults setBool:
        [retrievedAppInfo[@"scarletResidentSDKContract"] boolValue]
        forKey:@"Scarlet.ResidentSDKContract.V1"];
""", 1)
    liveprocess.write_text(source)

    boot = engine / "LiveContainer/LCBootstrap.m"
    original = boot.read_text()
    insert_before = "extern char **environ;\n"
    assert original.count(insert_before) == 1, "R6P11 LC main bootstrap anchor changed"
    helper = r"""
// R6P11: parse guest Mach-O's SDK declaration READ-ONLY, never its bundle ID,
// contents, signature, paths, entitlement or executable bytes for mutation.
static uint32_t ScarletGuestMachOSDKReadOnly(const char *path) {
    if(!path || !*path) return 0;
    __block uint32_t sdk = 0;
    NSString *parseError = LCParseMachO(path, true,
        ^(const char *filePath, struct mach_header_64 *header,
          int fd, void *filePtr) {
        if(!header || header->magic != MH_MAGIC_64 ||
           header->ncmds > 8192 || header->sizeofcmds > 1024*1024) return;
        uint32_t offset = 0;
        for(uint32_t i = 0; i < header->ncmds; i++) {
            if(offset > header->sizeofcmds ||
               header->sizeofcmds - offset < sizeof(struct load_command)) break;
            struct load_command *command = (struct load_command *)
                ((uint8_t *)(header + 1) + offset);
            if(command->cmdsize < sizeof(struct load_command) ||
               command->cmdsize > header->sizeofcmds - offset) break;
            if(command->cmd == LC_BUILD_VERSION &&
               command->cmdsize >= sizeof(struct build_version_command)) {
                struct build_version_command *build =
                    (struct build_version_command *)command;
                if(build->platform == PLATFORM_IOS) sdk = build->sdk;
            } else if(command->cmd == LC_VERSION_MIN_IPHONEOS &&
                      command->cmdsize >= sizeof(struct version_min_command) &&
                      sdk == 0) {
                sdk = ((struct version_min_command *)command)->sdk;
            }
            offset += command->cmdsize;
        }
    });
    return parseError ? 0 : sdk;
}
static void ScarletRecordGuestSDKContract(uint32_t sdk, NSString *origin) {
    NSUserDefaults *store = NSUserDefaults.lcSharedDefaults;
    if(!store || !origin || !sdk) return;
    NSString *key = @"Scarlet.Guest.SDKContract.V1";
    NSData *previous = [store dataForKey:key];
    NSMutableArray *rows = [NSMutableArray array];
    if(previous) {
        id decoded = [NSJSONSerialization JSONObjectWithData:previous
            options:NSJSONReadingMutableContainers error:NULL];
        if([decoded isKindOfClass:NSArray.class]) [rows addObjectsFromArray:decoded];
    }
    [rows addObject:@{
        @"id": NSUUID.UUID.UUIDString,
        @"epoch": @([[NSDate date] timeIntervalSince1970]),
        @"pid": @(getpid()),
        @"sdk_major": @((sdk >> 16) & 0xffff),
        @"sdk_minor": @((sdk >> 8) & 0xff),
        @"origin": origin
    }];
    if(rows.count > 24)
        [rows removeObjectsInRange:NSMakeRange(0, rows.count - 24)];
    NSData *encoded = [NSJSONSerialization dataWithJSONObject:rows
        options:0 error:NULL];
    if(encoded) [store setObject:encoded forKey:key];
}
"""
    original = original.replace(insert_before, helper + "\n" + insert_before, 1)
    dyld_before = '    DyldHooksInit([guestAppInfo[@"hideLiveContainer"] boolValue], hookDlopen, [guestAppInfo[@"spoofSDKVersion"] unsignedIntValue]);'
    assert original.count(dyld_before) == 1, "R6P11 pinned dyld hook call changed"
    dyld_after = r"""    // R6P11: only opt-in resident LiveProcess, all guest apps identically.
    // Preserve any explicit user-level Spoof SDK Version preference.
    uint32_t explicitSDK = [guestAppInfo[@"spoofSDKVersion"] unsignedIntValue];
    uint32_t effectiveSDK = explicitSDK;
    BOOL residentSDK = isLiveProcess && !isSideStore &&
        [lcUserDefaults boolForKey:@"Scarlet.ResidentSDKContract.V1"];
    NSString *sdkOrigin = @"user_override";
    if(residentSDK && effectiveSDK == 0) {
        uint32_t declaredSDK = ScarletGuestMachOSDKReadOnly(appExecPath);
        uint32_t declaredMajor = (declaredSDK >> 16) & 0xffff;
        NSOperatingSystemVersion os = NSProcessInfo.processInfo.operatingSystemVersion;
        if(declaredMajor >= 11 && declaredMajor <= (uint32_t)os.majorVersion) {
            effectiveSDK = declaredSDK;
            sdkOrigin = @"guest_macho";
        } else {
            sdkOrigin = @"no_usable_sdk";
        }
    }
    if(residentSDK) {
        // A recorded contract means we *requested* SDK-compatible dyld
        // semantics. It does not assert that UIKit's cached traits changed.
        if(effectiveSDK) ScarletRecordGuestSDKContract(effectiveSDK, sdkOrigin);
        else ScarletRecordGuestSDKContract(0x00000001, @"no_usable_sdk");
    }
    DyldHooksInit([guestAppInfo[@"hideLiveContainer"] boolValue],
                  hookDlopen, effectiveSDK);"""
    original = original.replace(dyld_before, dyld_after, 1)
    boot.write_text(original)

    # The pinned LC SDK spoof machinery contains assert() on dyld symbol
    # format/signature. It used to be an optional user action, but an
    # automatic resident experiment must never SIGABRT when OS 27 dyld differs.
    # Fail closed on an unknown signature and continue other guest boot hooks.
    dyld = engine / "LiveContainer/Tweaks/Dyld.m"
    dyld_text = dyld.read_text()
    changes = (
        ("    assert(baseAddr != 0);", "    if(!baseAddr) return false;"),
        ("        assert(adrpExtraOffset != -1);",
         "        if(adrpExtraOffset == -1) return false;"),
        ("    assert(gdyldPtr != 0);", "    if(!gdyldPtr) return false;"),
        ("    assert(*(void**)gdyldPtr != 0);",
         "    if(!*(void**)gdyldPtr) return false;"),
        ("        assert((*ldrInstPtr2 & 0xBFC00000) == 0xB9400000);",
         "        if((*ldrInstPtr2 & 0xBFC00000) != 0xB9400000) return false;"),
        ("        assert(offset);", "        if(!offset) return false;"),
        ("    assert(versionMapPtr);", "    if(!versionMapPtr) return false;"),
        ("    assert(versionMapPtr[0] == 0x07db0901 && versionMapPtr[2] == 0x00050000);",
         "    if(versionMapPtr[0] != 0x07db0901 || versionMapPtr[2] != 0x00050000) return false;"),
        ("    assert(size);", "    if(!size) return false;"),
    )
    for old, new in changes:
        assert dyld_text.count(old) == 1, "Pinned dyld SDK guard changed: " + old
        dyld_text = dyld_text.replace(old, new, 1)
    # Old initGuestSDKVersionInfo failures aborted the rest of DyldHooksInit
    # including jitless_hook_dlopen. Preserve original fallback/launch.
    old = """        if(!initGuestSDKVersionInfo() ||
           !performHookDyldApi("dyld_program_sdk_at_least", 1, (void**)&orig_dyld_program_sdk_at_least, hook_dyld_program_sdk_at_least) ||
           !performHookDyldApi("dyld_get_program_sdk_version", 0, (void**)&orig_dyld_get_program_sdk_version, hook_dyld_get_program_sdk_version)) {
            return;
        }"""
    assert dyld_text.count(old) == 1, "Pinned SDK dyld hook gating changed"
    new = """        // Unknown dyld layout is not a guest-process fatal error.
        // Preserve the original jitless dlopen hook in all cases.
        if(initGuestSDKVersionInfo()) {
            BOOL firstHook = performHookDyldApi("dyld_program_sdk_at_least", 1,
                (void**)&orig_dyld_program_sdk_at_least, hook_dyld_program_sdk_at_least);
            BOOL secondHook = firstHook && performHookDyldApi("dyld_get_program_sdk_version", 0,
                (void**)&orig_dyld_get_program_sdk_version, hook_dyld_get_program_sdk_version);
            if(!secondHook) NSLog(@"[SCARLET_SDK_CONTRACT] dyld_hook_unavailable");
        } else {
            NSLog(@"[SCARLET_SDK_CONTRACT] dyld_version_map_unavailable");
        }"""
    dyld_text = dyld_text.replace(old, new, 1)
    dyld.write_text(dyld_text)

    return {
        "residentOnly": True, "noPerAppExceptions": True,
        "guestMachOReadOnly": True, "explicitSpoofUnchanged": True,
        "unchangedGuestGeometry": True,
        "dyldMissingSignatureFailClosed": True,
        "jitlessHookPreservedWhenSDKUnrecognized": True,
        "startupLimitation": "UIKit already loaded by NSExtensionMain; test on device"
    }


def add_scarlet_guest_launch_policy_probe(engine: Path) -> dict:
    """R6P7: inspect the launch-time *bundle policy*, not Safe Area/UIWindow.

    UIKit may cache app-level status bar and scene declarations at startup.
    LiveContainer substitutes its main NSBundle and CFBundle before calling
    the guest's main(); compare the original LiveProcess extension's declared
    policy with the guest bundle and the effective post-substitution main bundle.
    This observes only boolean/plist-presence facts. It changes no policies,
    guest process, viewport, UIWindow, overlay or signing.
    """
    target = engine / "LiveContainer/LCBootstrap.m"
    source = target.read_text()
    anchor = "bool sideStoreExist = false;\n"
    assert source.count(anchor) == 1, "Pinned LCBootstrap globals changed"
    helper = r'''
// R6P7: launch-policy differential, not a UIKit or Safe Area modification.
// No identifiers, guest names, paths, view tree or screenshots are exported.
static NSNumber *ScarletPolicyFlag(NSDictionary *dict, NSString *key) {
    id value = dict[key];
    return [value respondsToSelector:@selector(boolValue)]
        ? @([value boolValue]) : @(-1);
}

static NSNumber *ScarletPolicyOrientationCount(NSDictionary *dict) {
    id arr = dict[@"UISupportedInterfaceOrientations"];
    return [arr isKindOfClass:NSArray.class] ? @([(NSArray *)arr count]) : @(-1);
}

static void ScarletGuestLaunchPolicySnapshot(NSString *stage,
                                               NSBundle *guestBundle) {
    if(!isLiveProcess || !guestBundle || !lcSharedDefaults) return;
    NSDictionary *host = lcMainBundle.infoDictionary ?: @{};
    NSDictionary *guest = guestBundle.infoDictionary ?: @{};
    NSDictionary *actual = NSBundle.mainBundle.infoDictionary ?: @{};
    CFBundleRef cf = CFBundleGetMainBundle();
    NSDictionary *core = cf ? (__bridge NSDictionary *)CFBundleGetInfoDictionary(cf) : @{};
    if(!core) core = @{};
    // -1 means undeclared: do not conflate a missing key with false.
    NSDictionary *snapshot = @{
        @"id": NSUUID.UUID.UUIDString,
        @"epoch": @([[NSDate date] timeIntervalSince1970]),
        @"pid": @(getpid()), @"stage": stage,
        @"host_status_hidden": ScarletPolicyFlag(host, @"UIStatusBarHidden"),
        @"guest_status_hidden": ScarletPolicyFlag(guest, @"UIStatusBarHidden"),
        @"actual_status_hidden": ScarletPolicyFlag(actual, @"UIStatusBarHidden"),
        @"cf_status_hidden": ScarletPolicyFlag(core, @"UIStatusBarHidden"),
        @"host_controller_status": ScarletPolicyFlag(host, @"UIViewControllerBasedStatusBarAppearance"),
        @"guest_controller_status": ScarletPolicyFlag(guest, @"UIViewControllerBasedStatusBarAppearance"),
        @"actual_controller_status": ScarletPolicyFlag(actual, @"UIViewControllerBasedStatusBarAppearance"),
        @"host_fullscreen": ScarletPolicyFlag(host, @"UIRequiresFullScreen"),
        @"guest_fullscreen": ScarletPolicyFlag(guest, @"UIRequiresFullScreen"),
        @"actual_fullscreen": ScarletPolicyFlag(actual, @"UIRequiresFullScreen"),
        @"host_scene_manifest": @(host[@"UIApplicationSceneManifest"] != nil),
        @"guest_scene_manifest": @(guest[@"UIApplicationSceneManifest"] != nil),
        @"actual_scene_manifest": @(actual[@"UIApplicationSceneManifest"] != nil),
        @"host_orientations": ScarletPolicyOrientationCount(host),
        @"guest_orientations": ScarletPolicyOrientationCount(guest),
        @"actual_orientations": ScarletPolicyOrientationCount(actual)
    };
    NSData *previous = [lcSharedDefaults dataForKey:@"Scarlet.Guest.LaunchPolicy.V1"];
    NSMutableArray *items = [NSMutableArray array];
    if(previous) {
        id decoded = [NSJSONSerialization JSONObjectWithData:previous
            options:NSJSONReadingMutableContainers error:NULL];
        if([decoded isKindOfClass:NSArray.class]) [items addObjectsFromArray:decoded];
    }
    [items addObject:snapshot];
    if(items.count > 16)
        [items removeObjectsInRange:NSMakeRange(0, items.count - 16)];
    NSData *encoded = [NSJSONSerialization dataWithJSONObject:items
        options:0 error:NULL];
    if(encoded) [lcSharedDefaults setObject:encoded
                                    forKey:@"Scarlet.Guest.LaunchPolicy.V1"];
}
'''
    source = source.replace(anchor, anchor + helper, 1)
    before = '''    // Overwrite NSBundle
    overwriteMainNSBundle(appBundle);

    // Overwrite CFBundle
    overwriteMainCFBundle();
'''
    after = '''    // R6P7: compare original LiveProcess launch metadata with the guest
    // before and after main bundle substitution. Do not mutate either.
    ScarletGuestLaunchPolicySnapshot(@"before_bundle_swap", appBundle);
    // Overwrite NSBundle
    overwriteMainNSBundle(appBundle);

    // Overwrite CFBundle
    overwriteMainCFBundle();
    ScarletGuestLaunchPolicySnapshot(@"after_bundle_swap", appBundle);
'''
    assert source.count(before) == 1, "Pinned LCBootstrap bundle-swap changed"
    source = source.replace(before, after, 1)
    if "#include <unistd.h>" not in source:
        source = source.replace("#include <stdlib.h>", "#include <stdlib.h>\n#include <unistd.h>", 1)
    target.write_text(source)
    return {
        "recordKey": "Scarlet.Guest.LaunchPolicy.V1",
        "source": str(target.relative_to(engine)),
        "readOnly": True,
        "bundleSwapStages": 2,
        "noViewportOrSafeAreaChanges": True
    }


def add_scarlet_guest_audio_isolation(engine: Path) -> dict:
    """V48-R6: keep only the active LiveProcess guest's audio session alive.

    Every guest is a separate LiveProcess extension process, so the host's
    AVAudioSession cannot silence another guest. The host posts a Darwin
    notification scoped to the exact guest PID; the injected TweakLoader hook
    in that process posts the standard interruption/resign-active lifecycle
    and deactivates only its own audio session. Processes and RAM are kept.
    """
    source = r'''// SCARLET_GUEST_AUDIO_ISOLATION_V1
// Runs inside each LiveProcess guest through TweakLoader. The host can only
// name the guest by its exact PID; no host audio session or guest process is
// touched here. Deactivating the guest's own session stops mixed background
// audio without terminating or suspending the retained LiveProcess.
#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#include <unistd.h>
#import "utils.h"

// This file runs inside an app extension. UIApplication.sharedApplication is
// unavailable there, so the standard lifecycle notifications are posted by
// their documented names with a nil object instead.
static NSNotificationName const ScarletUIBecameActiveNotification =
    @"UIApplicationDidBecomeActiveNotification";
static NSNotificationName const ScarletUIResignActiveNotification =
    @"UIApplicationWillResignActiveNotification";

static BOOL scarletGuestAudioPaused = NO;
static int scarletGuestAudioObserver = 0;

// Darwin notifications do not carry a cross-process userInfo dictionary.
// The receipt name encodes only action, result, and this LiveProcess PID.
// A receipt reports AVAudioSession setActive's return value; it is NOT
// an acoustic microphone measurement nor proof that every media API stopped.
static void ScarletGuestAudioReceipt(BOOL active, BOOL success) {
    NSString *name = [NSString stringWithFormat:
        @"com.scarlet.guest.audio.ack.%@.%@.%d",
        active ? @"resume" : @"pause", success ? @"ok" : @"error", getpid()];
    CFNotificationCenterPostNotification(
        CFNotificationCenterGetDarwinNotifyCenter(),
        (__bridge CFStringRef)name, NULL, NULL, true);
}

static void ScarletGuestAudioRetryPause(int attempt) {
    if(!scarletGuestAudioPaused) return;
    NSError *error = nil;
    BOOL result = [AVAudioSession.sharedInstance setActive:NO
        withOptions:AVAudioSessionSetActiveOptionNotifyOthersOnDeactivation
        error:&error];
    NSLog(@"[SCARLET_AUDIO] guest pid=%d pause attempt=%d result=%d code=%ld",
          getpid(), attempt, result ? 1 : 0, (long)error.code);
    ScarletGuestAudioReceipt(NO, result);
    // R6P4: do not treat a failed deactivation as if the guest is silent.
    // Retry within the same LiveProcess, without resigning or killing it.
    if(!result && attempt < 2) {
        int delayMs = attempt == 0 ? 300 : 900;
        dispatch_after(dispatch_time(DISPATCH_TIME_NOW,
            (int64_t)delayMs * NSEC_PER_MSEC), dispatch_get_main_queue(), ^{
                if(scarletGuestAudioPaused) ScarletGuestAudioRetryPause(attempt + 1);
            });
    }
}

static void ScarletGuestAudioApply(BOOL active) {
    AVAudioSession *session = AVAudioSession.sharedInstance;
    NSError *error = nil;
    if(active) {
        if(!scarletGuestAudioPaused) {
            ScarletGuestAudioReceipt(YES, YES); // Already unpaused.
            return;
        }
        scarletGuestAudioPaused = NO;
        BOOL result = [session setActive:YES error:&error];
        [[NSNotificationCenter defaultCenter]
            postNotificationName:AVAudioSessionInterruptionNotification
            object:session
            userInfo:@{AVAudioSessionInterruptionTypeKey:
                           @(AVAudioSessionInterruptionTypeEnded),
                       AVAudioSessionInterruptionOptionKey:
                           @(AVAudioSessionInterruptionOptionShouldResume)}];
        [[NSNotificationCenter defaultCenter]
            postNotificationName:ScarletUIBecameActiveNotification
            object:nil];
        ScarletGuestAudioReceipt(YES, result);
        NSLog(@"[SCARLET_AUDIO] guest pid=%d resume result=%d code=%ld",
              getpid(), result ? 1 : 0, (long)error.code);
    } else {
        if(!scarletGuestAudioPaused) {
            scarletGuestAudioPaused = YES;
            [[NSNotificationCenter defaultCenter]
                postNotificationName:AVAudioSessionInterruptionNotification
                object:session
                userInfo:@{AVAudioSessionInterruptionTypeKey:
                               @(AVAudioSessionInterruptionTypeBegan)}];
            [[NSNotificationCenter defaultCenter]
                postNotificationName:ScarletUIResignActiveNotification
                object:nil];
        }
        // Always reassert the pause, including if an earlier call failed:
        // the previous implementation ignored all later pause requests.
        ScarletGuestAudioRetryPause(0);
    }
}

static void ScarletGuestAudioPauseCallback(CFNotificationCenterRef center,
                                           void *observer,
                                           CFNotificationName name,
                                           const void *object,
                                           CFDictionaryRef userInfo) {
    dispatch_async(dispatch_get_main_queue(), ^{ ScarletGuestAudioApply(NO); });
}

static void ScarletGuestAudioResumeCallback(CFNotificationCenterRef center,
                                            void *observer,
                                            CFNotificationName name,
                                            const void *object,
                                            CFDictionaryRef userInfo) {
    dispatch_async(dispatch_get_main_queue(), ^{ ScarletGuestAudioApply(YES); });
}

void initScarletGuestAudioIsolation(void) {
    if(!NSUserDefaults.isLiveProcess) return;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        int pid = getpid();
        NSString *pauseName = [NSString stringWithFormat:
            @"com.scarlet.guest.audio.pause.%d", pid];
        NSString *resumeName = [NSString stringWithFormat:
            @"com.scarlet.guest.audio.resume.%d", pid];
        CFNotificationCenterRef center = CFNotificationCenterGetDarwinNotifyCenter();
        CFNotificationCenterAddObserver(center, &scarletGuestAudioObserver,
            ScarletGuestAudioPauseCallback,
            (__bridge CFStringRef)pauseName, NULL,
            CFNotificationSuspensionBehaviorDeliverImmediately);
        CFNotificationCenterAddObserver(center, &scarletGuestAudioObserver,
            ScarletGuestAudioResumeCallback,
            (__bridge CFStringRef)resumeName, NULL,
            CFNotificationSuspensionBehaviorDeliverImmediately);
        NSLog(@"[SCARLET_AUDIO] guest isolation armed pid=%d", pid);
    });
}
'''
    tweaks = engine/"LiveContainer/Tweaks"
    target = tweaks/"ScarletGuestAudioIsolation.m"
    assert tweaks.is_dir(), "Pinned LiveContainer Tweaks folder missing"
    target.write_text(source)

    header = tweaks/"Tweaks.h"
    header_source = header.read_text()
    declaration = "void initScarletGuestAudioIsolation(void);\n"
    if declaration not in header_source:
        anchor = "void initDead10ccFix(void);\n"
        assert header_source.count(anchor) == 1, "Pinned Tweaks.h anchor changed"
        header_source = header_source.replace(anchor, anchor + declaration, 1)
        header.write_text(header_source)

    bootstrap = engine/"LiveContainer/LCBootstrap.m"
    bootstrap_source = bootstrap.read_text()
    call = "        initScarletGuestAudioIsolation();\n"
    if call not in bootstrap_source:
        anchor = "        initDead10ccFix();\n"
        assert bootstrap_source.count(anchor) == 1, "Pinned LCBootstrap init anchor changed"
        bootstrap_source = bootstrap_source.replace(anchor, anchor + call, 1)
        bootstrap.write_text(bootstrap_source)
    return {
        "guestProcessScoped": True,
        "hostAudioSessionUntouched": True,
        "guestProcessKeptAlive": True,
        "notificationPrefix": "com.scarlet.guest.audio",
        "source": str(target.relative_to(engine)),
        "sha256": file_sha(target),
    }



def add_scarlet_guest_keyboard_handoff(engine: Path) -> dict:
    """R6P24: outgoing remote guest resigns its own editor before a switch."""
    source=Path(__file__).with_name("ScarletGuestKeyboardHandoff.m.txt")
    target=engine/"LiveContainer/Tweaks/ScarletGuestKeyboardHandoff.m"
    assert source.is_file() and target.parent.is_dir()
    target.write_bytes(source.read_bytes())
    header=engine/"LiveContainer/Tweaks/Tweaks.h"
    body=header.read_text()
    anchor="void initScarletGuestIslandContentGuard(void);\n"
    assert body.count(anchor)==1
    header.write_text(body.replace(anchor,
        anchor+"void initScarletGuestKeyboardHandoff(void);\n",1))
    bootstrap=engine/"LiveContainer/LCBootstrap.m"
    body=bootstrap.read_text()
    anchor="        initScarletGuestIslandContentGuard();\n"
    assert body.count(anchor)==1
    bootstrap.write_text(body.replace(anchor,
        anchor+"        initScarletGuestKeyboardHandoff();\n",1))
    return {
        "residentOnly": True, "outgoingGuestOnly": True,
        "firstResponderRelease": True, "keyboardDidHideObserved": True,
        "guestProcessKeptAlive": True, "source":str(target.relative_to(engine)),
        "sha256":file_sha(target),
    }

def add_scarlet_guest_island_content_guard(engine: Path) -> dict:
    # R6P15: only at the guest's own UIKit root, not host FBScene geometry.
    target = engine / "LiveContainer/Tweaks/ScarletGuestIslandContentGuard.m"
    source = Path(__file__).with_name("ScarletGuestIslandContentGuard.m.txt")
    assert source.is_file() and target.parent.is_dir()
    target.write_bytes(source.read_bytes())
    header = engine / "LiveContainer/Tweaks/Tweaks.h"
    text = header.read_text()
    anchor = "void initScarletGuestAudioIsolation(void);\n"
    assert text.count(anchor) == 1
    header.write_text(text.replace(
        anchor, anchor + "void initScarletGuestIslandContentGuard(void);\n", 1))
    boot = engine / "LiveContainer/LCBootstrap.m"
    text = boot.read_text()
    anchor = "        initScarletGuestAudioIsolation();\n"
    assert text.count(anchor) == 1
    boot.write_text(text.replace(
        anchor, anchor + "        initScarletGuestIslandContentGuard();\n", 1))
    return {"residentOnly": True, "windowResized": False,
            "globalUIKitHook": False, "guestSource": str(target),
            "sha256": file_sha(target)}


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
        root/"rebuild/HostApp/ScarletFeatureModulesSection.swift":"ScarletFeatureModulesSection.swift",
        root/"rebuild/HostApp/ScarletAutomaticRenewal.swift":"ScarletAutomaticRenewal.swift",
        root/"rebuild/HostApp/ScarletNativeDevicePairing.swift":"ScarletNativeDevicePairing.swift",
        root/"rebuild/HostApp/ScarletSigningReadinessPanel.swift":"ScarletSigningReadinessPanel.swift",
        root/"rebuild/HostApp/ScarletGuestSwitcherOverlay.swift":"ScarletGuestSwitcherOverlay.swift",
        root/"rebuild/HostApp/ScarletFullscreenGuestTab.swift":"ScarletFullscreenGuestTab.swift",
        root/"rebuild/HostApp/ScarletFullscreenSceneStack.swift":"ScarletFullscreenSceneStack.swift",
        root/"rebuild/HostApp/ScarletGuestSessionLedger.swift":"ScarletGuestSessionLedger.swift",
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
    # Register a native BG refresh handler during LC's original app launch.
    delegate_file=engine/"LiveContainerSwiftUI/App/AppDelegate.swift"
    delegate=delegate_file.read_text()
    launch='        application.shortcutItems = nil\n        UserDefaults.standard.removeObject(forKey: "LCNeedToAcquireJIT")\n'
    assert delegate.count(launch)==1, "Pinned LC AppDelegate changed"
    delegate=delegate.replace(launch,launch+
        "        if #available(iOS 17.0, *) {\n"+
        "            ScarletAutomaticRenewal.shared.registerAtLaunch()\n"+
        "        }\n"+
        "        if #available(iOS 27.0, *) {\n"+
        "            ScarletDevicePairingModel.shared.registerAtLaunch()\n"+
        "        }\n",1)
    delegate_file.write_text(delegate)
    # Keep every original Info.plist entry; grant only our BG task identifier.
    import plistlib
    info_file=engine/"LiveContainer/Info.plist"
    with info_file.open("rb") as handle: info=plistlib.load(handle)
    identifiers=list(info.get("BGTaskSchedulerPermittedIdentifiers",[]))
    identifier="com.kdt.livecontainer.P8EZT3U5N4.refresh"
    if identifier not in identifiers: identifiers.append(identifier)
    pairingTaskID="com.kdt.livecontainer.P8EZT3U5N4.pairing"
    if pairingTaskID not in identifiers: identifiers.append(pairingTaskID)
    # The user's signing tool has also produced an observed app bundle ID
    # with one appended team suffix; iOS BG task identifiers are scoped to
    # that installed app. Declare BOTH exact permitted variants without
    # changing the app identity or creating new Apple entitlement rights.
    observedBundle="com.kdt.livecontainer.P8EZT3U5N4.P8EZT3U5N4"
    for suffix in ("refresh", "pairing"):
        allowedID=f"{observedBundle}.{suffix}"
        if allowedID not in identifiers: identifiers.append(allowedID)
    info["BGTaskSchedulerPermittedIdentifiers"]=identifiers
    info["NSLocalNetworkUsageDescription"]=(
        "Scarlet Crystal은 iOS 27에서 기기 페어링을 생성하고 "
        "내장 SideStore의 갱신 연결을 검증하기 위해 로컬 네트워크를 사용합니다.")
    bonjour=list(info.get("NSBonjourServices",[]))
    service="_remotepairing-pairable-host._tcp"
    if service not in bonjour: bonjour.append(service)
    info["NSBonjourServices"]=bonjour
    assert "fetch" in info.get("UIBackgroundModes",[])
    with info_file.open("wb") as handle: plistlib.dump(info,handle)
    recorder = out / "ScarletDiagnosticRecorder.swift"
    report_source = recorder.read_text()
    marker = "__SCARLET_BUILD_SHA__"
    assert report_source.count(marker) == 1, "Diagnostic build identity anchor changed"
    runner_sha = os.environ.get("GITHUB_SHA", "").strip()
    build_sha = runner_sha[:12].lower() if re.fullmatch(r"[0-9a-fA-F]{40}", runner_sha) else "local-unverified"
    recorder.write_text(report_source.replace(marker, build_sha))
    # R6P10: a one-file user diagnostic report must contain all earlier
    # interventions with file/function, original and replacement source code,
    # verification grade, and the complete AI no-repeat instructions.
    # Embed the repo-reviewed JSON/prompt at archive time, not by trying to
    # recover old JSONL files (rotated) or fetching external URLs on iPhone.
    history_path = root/"rebuild/diagnostics/scarlet_remediation_history.json"
    handoff_path = root/"rebuild/diagnostics/SCARLET_LOG_ONLY_HANDOFF_PROMPT.md"
    audit = json.loads(history_path.read_text(encoding="utf-8"))
    assert audit["schema"] >= 2 and len(audit["entries"]) >= 45, "Repair ledger unexpectedly truncated"
    ids = [e["id"] for e in audit["entries"]]
    assert len(ids) == len(set(ids)), "Repair history contains duplicate IDs"
    for item in audit["entries"]:
        assert "source_verification" in item and "code_locations" in item, (
            "Repair history lacks source traceability: " + item["id"])
        if item["source_verification"] == "git_patch_observed":
            assert item["code_locations"], "Source-verified entry missing source diff: " + item["id"]
            for source in item["code_locations"]:
                assert source.get("file") and source.get("location"), (
                    "Changed file/line missing: " + item["id"])
                assert source.get("before") or source.get("after"), (
                    "Before/after source missing: " + item["id"])
    r = recorder.read_text(encoding="utf-8")
    for token, source_bytes in (
        ("__SCARLET_REMEDIATION_HISTORY_B64__", history_path.read_bytes()),
        ("__SCARLET_HANDOFF_PROMPT_B64__", handoff_path.read_bytes()),
    ):
        assert r.count(token) == 1, "Diagnostic ledger embed anchor changed: " + token
        r = r.replace(token, base64.b64encode(source_bytes).decode("ascii"), 1)
    recorder.write_text(r, encoding="utf-8")
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

    # Overlay only: the PR48 default runApp() relaunches an entire guest
    # process and does NOT create a MultitaskAppWindow. Inject the floating
    # control via existing guest UIKit hook after its UIApplication is active.
    # Avoid touching guest bounds, transforms, orientation policies, host tabs.
    guest_hook_file = engine/"TweakLoader/UIKit+GuestHooks.m"
    assert guest_hook_file.is_file(), "Pinned LC guest UIKit hook missing"
    guest_hook_source = guest_hook_file.read_text()
    guest_hook_anchor = "    if(!NSUserDefaults.lcGuestAppId) return;\n"
    assert guest_hook_source.count(guest_hook_anchor)==1, "Guest hook changed"
    guest_hook_source = guest_hook_source.replace(
        '#import "Localization.h"\n',
        '#import "Localization.h"\n#import <objc/message.h>\n#import <dlfcn.h>\n')
    # This can execute before the SwiftUI framework exists. The host can
    # distinguish a missing TweakLoader hook from a broken Swift overlay.
    # Only fixed event names; bounded to 48, and never a guest title/ID.
    hook_probe_anchor = "UIInterfaceOrientation LCOrientationLock = UIInterfaceOrientationUnknown;\n"
    assert guest_hook_source.count(hook_probe_anchor) == 1
    hook_probe_helper = """
static void ScarletGuestHookTrace(NSString *event) {
    static NSSet *allowed;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        allowed = [NSSet setWithArray:@[@"hook_entered", @"framework_loaded",
            @"framework_missing", @"provider_ready", @"provider_missing"]];
    });
    if(![allowed containsObject:event]) return;
    NSUserDefaults *shared = NSUserDefaults.lcSharedDefaults;
    if(!shared) return;
    NSData *raw = [shared dataForKey:@"Scarlet.Guest.SwitcherTrace.V20"];
    NSMutableArray *entries = [NSMutableArray array];
    if(raw) {
        id previous = [NSJSONSerialization JSONObjectWithData:raw
            options:NSJSONReadingMutableContainers error:NULL];
        if([previous isKindOfClass:NSArray.class]) [entries addObjectsFromArray:previous];
    }
    [entries addObject:@{@"id":NSUUID.UUID.UUIDString,
                         @"event":event, @"count":@0,
                         @"createdAt":@([[NSDate date] timeIntervalSinceReferenceDate])}];
    if(entries.count > 48) {
        [entries removeObjectsInRange:NSMakeRange(0, entries.count - 48)];
    }
    NSData *encoded = [NSJSONSerialization dataWithJSONObject:entries options:0 error:NULL];
    if(encoded) {
        [shared setObject:encoded forKey:@"Scarlet.Guest.SwitcherTrace.V20"];
        if(![[shared dataForKey:@"Scarlet.Guest.SwitcherTrace.V20"] isEqualToData:encoded]) {
            NSLog(@"[SCARLET_GUEST_TAB] shared_trace_readback_failed");
        }
    }
}

"""
    guest_hook_source = guest_hook_source.replace(
        hook_probe_anchor, hook_probe_helper + hook_probe_anchor)
    guest_hook_source = guest_hook_source.replace(
        guest_hook_anchor,
        guest_hook_anchor +
        "    ScarletGuestHookTrace(@\"hook_entered\");\n"
        "    // The full-screen LC guest skips LiveContainerSwiftUI's main().\n"
        "    // Its classes are in a separate dylib, not in the main executable.\n"
        "    // Explicitly load the exact built-in framework before NSClassFromString.\n"
        "    if(!NSUserDefaults.isLiveProcess) {\n"
        "        NSString *frameworkPath = [NSUserDefaults.lcMainBundle.bundlePath\n"
        "            stringByAppendingPathComponent:@\"Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI\"];\n"
        "        void *framework = dlopen(frameworkPath.UTF8String, RTLD_LAZY | RTLD_GLOBAL);\n"
        "        if(!framework) {\n"
        "            NSLog(@\"[SCARLET_GUEST_TAB] framework_unavailable\");\n"
        "            ScarletGuestHookTrace(@\"framework_missing\");\n"
        "        } else {\n"
        "            NSLog(@\"[SCARLET_GUEST_TAB] framework_loaded\");\n"
        "            ScarletGuestHookTrace(@\"framework_loaded\");\n"
        "        }\n"
        "        void (^mount)(void) = ^{\n"
        "            Class provider = NSClassFromString(@\"ScarletFullscreenGuestTabInstaller\");\n"
        "            SEL callback = NSSelectorFromString(@\"installForGuestName:\");\n"
        "            if (provider && [provider respondsToSelector:callback]) {\n"
        "                static BOOL providerTraced = NO;\n"
        "                if(!providerTraced) { providerTraced = YES; ScarletGuestHookTrace(@\"provider_ready\"); }\n"
        "                // A display name is not a stable guest identity.\n"
        "                // LC clears selected during bootstrap, but this\n"
        "                // runtime bundle ID remains authoritative.\n"
        "                NSString *guestID = NSUserDefaults.lcGuestAppId;\n"
        "                ((void(*)(id,SEL,id))objc_msgSend)(provider,callback,guestID);\n"
        "            } else {\n"
        "                NSLog(@\"[SCARLET_GUEST_TAB] installer_class_unavailable\");\n"
        "                static BOOL providerMissingTraced = NO;\n"
        "                if(!providerMissingTraced) { providerMissingTraced = YES; ScarletGuestHookTrace(@\"provider_missing\"); }\n"
        "            }\n"
        "        };\n"
        "        for(NSNotificationName name in @[UIApplicationDidBecomeActiveNotification,\n"
        "              UIWindowDidBecomeKeyNotification, UISceneDidActivateNotification]) {\n"
        "            [[NSNotificationCenter defaultCenter] addObserverForName:name\n"
        "              object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {\n"
        "                mount();\n"
        "            }];\n"
        "        }\n"
        "        for(NSNumber *delay in @[@0.2,@0.75,@1.5,@3.0]) {\n"
        "            dispatch_after(dispatch_time(DISPATCH_TIME_NOW,(int64_t)(delay.doubleValue * NSEC_PER_SEC)),\n"
        "                           dispatch_get_main_queue(), mount);\n"
        "        }\n"
        "    }\n")
    guest_hook_file.write_text(guest_hook_source)

    # V36 removes the root cause at source-level rather than attaching or
    # hiding the old LC dock from host UIKit.
    legacy_visuals = remove_upstream_legacy_window_ui(engine)
    fullscreen_slot = add_v45_fullscreen_scene_slot(engine)
    deferred_scene_boot = add_r6p9_deferred_liveprocess_boot(engine)
    resident_sdk_contract = add_r6p11_guest_sdk_contract(engine)
    guest_audio = add_scarlet_guest_audio_isolation(engine)
    island_content = add_scarlet_guest_island_content_guard(engine)
    keyboard_handoff = add_scarlet_guest_keyboard_handoff(engine)
    guest_launch_policy = add_scarlet_guest_launch_policy_probe(engine)
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
        "onDeviceSigtrapDockForceUnwrapGuarded":False,
        "legacyVisualSourceRemoved":True,
        "legacyVisualRemoval":legacy_visuals,
        "experimentalResidentFullscreenViewport": fullscreen_slot,
        "deferredRemoteLaunchUntilHosted": deferred_scene_boot,
        "residentGuestSDKContract": resident_sdk_contract,
        "guestAudioIsolation": guest_audio,
        "guestKeyboardHandoff": keyboard_handoff,
        "guestLaunchPolicyDifferential": guest_launch_policy,
        "dockAttachDeferredToWindowVisibility":False,
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
