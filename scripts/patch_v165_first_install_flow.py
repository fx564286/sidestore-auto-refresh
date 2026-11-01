#!/usr/bin/env python3
"""V165: first-install one-primary-action UI, single inbox-file import, no third-party pairing code.

Runs on the host-owned V3UnifiedShell after V164, not SideStore's headless UI.
Keeps V163 glass UI and V164 RemotePairing unchanged. No hidden authentication,
no automatic trust grants and no secret-bearing debug messages.
"""
from pathlib import Path
import sys

SWIFT = Path('LiveContainerSwiftUI/Views/V3UnifiedShell.swift')
MARK = 'SCARLET_V165_FIRST_INSTALL'

def one(s, old, new, label):
    n=s.count(old)
    if n!=1: raise ValueError(f'V165 {label} anchor drift: {n}')
    return s.replace(old,new,1)

def patch(s):
    if MARK in s:
        for term in ('SCARLET_V165_INBOX_REUSE','SCARLET_V165_SINGLE_NEXT_ACTION',
                     'SCARLET_V165_LEGACY_HELP_COLLAPSED'):
            if term not in s: raise ValueError('V165 partial flow: '+term)
        if s.count('SCARLET_V165_FIRST_INSTALL:')!=1:
            raise ValueError('V165 duplicate flow')
        return s
    for term in ('V3_PAIRING_PLACEMENT_FIRST_V1','V3_SETUP_COMPLETION_POLICY_V1',
                 'V3_PAIRING_IMPORT_IS_FALLBACK_V1','V3_RECHECK_PAIRING_ON_RETURN_V1'):
        if term not in s: raise ValueError('V165 missing V164 shell prerequisite: '+term)

    # First launch: open the existing Setup Assistant once, only from an
    # authoritative bridge snapshot and only when setup really is outstanding.
    # Previously installed/signed-in devices are never prompted on upgrade.
    first_root = s.index('struct V3UnifiedTabs: View {')
    before, root = s[:first_root], s[first_root:]
    anchor = '''            await status.cleanupOrphanedStagedIPAs()
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification))'''
    replacement = '''            await status.cleanupOrphanedStagedIPAs()
            // SCARLET_V165_FIRST_LAUNCH: no destructive setup and no
            // optimistic "ready" status; only one consent-aware entry.
            if !UserDefaults.standard.bool(forKey: "ScarletV165InitialSetupOpened") {
                let observation = await status.reloadAndWait()
                if V3SetupReloadRecomputePolicy.mayRecompute(
                        outcome: observation.setupSnapshotOutcome) {
                    let missingPairing = V3PairingPresentationPolicy.state(
                        statusConnected: status.connected, pairingStatus: status.pairing) == .unsatisfied
                    let actionable = missingPairing || status.needsSignIn
                    if actionable, !status.setupPresented, !status.signInPresented,
                       status.presentation == nil, !status.loading {
                        UserDefaults.standard.set(true, forKey: "ScarletV165InitialSetupOpened")
                        status.setupPresented = true
                    }
                }
            }
        }
        .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification))'''
    root=one(root,anchor,replacement,'on first install enter setup')
    s=before+root

    # Make received pairing records available in one tap without browsing the
    # Files picker again. Deliberately never overwrite an existing good record
    # automatically, and refuse ambiguous multiple candidate files.
    s=one(s, '''    @State private var working = false
    var body: some View {
        List {
            Section("Status") {''', '''    @State private var working = false
    @State private var receivedPairingFile: URL?
    // SCARLET_V165_INBOX_REUSE: an explicit iOS Share-to-app file is in this
    // app's own Inbox; no private file-provider scanning or secret disclosure.
    // Exactly one candidate is required; multiple files need a user choice.
    private static func oneReceivedPairingFile() -> URL? {
        guard let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first else {
            return nil
        }
        let inbox = documents.appendingPathComponent("Inbox", isDirectory: true)
        guard let names = try? FileManager.default.contentsOfDirectory(at: inbox,
            includingPropertiesForKeys: [.isRegularFileKey], options: [.skipsHiddenFiles]) else { return nil }
        let eligible = names.filter { file in
            let ext = file.pathExtension.lowercased()
            return (ext == "mobiledevicepairing" || ext == "plist") &&
                ((try? file.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile) == true)
        }
        return eligible.count == 1 ? eligible[0] : nil
    }
    var body: some View {
        List {
            Section("Status") {''', 'inbox reuse state')
    s=one(s, '''            // V3_PAIRING_PLACEMENT_FIRST_V1: the pairing mechanism works. The
            // normal installation workflow places the pairing file with the tool''', '''            // SCARLET_V165_FIRST_INSTALL: keep one preferred path and use
            // installed pairing automatically when the authoritative service
            // reports it. Never claim trust/pairing succeeded before UDID proof.
            // V3_PAIRING_PLACEMENT_FIRST_V1: the pairing mechanism works. The
            // normal installation workflow places the pairing file with the tool''', 'main marker')
    block='''                    Text("Recommended setup")
                        .font(.footnote.weight(.semibold))
                    Text("If you installed with iLoader:")
                        .font(.footnote).foregroundColor(.secondary)
                    ForEach(Array(Self.pairingPlacementSteps.enumerated()), id: \\.offset) { index, step in
                        HStack(alignment: .firstTextBaseline, spacing: 8) {
                            Text("\\(index + 1).").font(.caption).foregroundColor(.secondary)
                            Text(step).font(.footnote)
                        }
                    }
                    Text("Other installation tools use different menu names, but they all place the pairing file for the installed app.")
                        .font(.caption).foregroundColor(.secondary)'''
    alt='''                    Text("Existing pairing is reused automatically. If this is a new install, finish the Apple-approved pairing step in your installer once.")
                        .font(.footnote).foregroundColor(.secondary)
                    if let receivedPairingFile {
                        Button {
                            Task { await importFile(receivedPairingFile) }
                        } label: {
                            Label("Use Received Pairing File", systemImage: "doc.badge.checkmark")
                        }
                        .disabled(working)
                        .accessibilityIdentifier("scarletV165UseReceivedPairing")
                    }
                    Button("Choose a Pairing File") { pickerPresented = true }
                        .disabled(working)
                    // SCARLET_V165_LEGACY_HELP_COLLAPSED: legacy computer
                    // placement instructions remain available on demand.
                    DisclosureGroup("Advanced: computer-assisted pairing") {
                        ForEach(Array(Self.pairingPlacementSteps.enumerated()), id: \\.offset) { index, step in
                            HStack(alignment: .firstTextBaseline, spacing: 8) {
                                Text("\\(index + 1).").font(.caption).foregroundColor(.secondary)
                                Text(step).font(.footnote)
                            }
                        }
                    }
                    Text("iOS 27 may require Remote Pairing rather than a classic USB-only record. Connection is not verified until the device service responds.")
                        .font(.caption).foregroundColor(.secondary)'''
    s=one(s,block,alt,'collapse 9 step instructions')
    s=one(s,'''        .sheet(isPresented: $pickerPresented) {
            V3FilePicker(types: ["com.apple.property-list", "public.xml", "public.data"]) { url in
                pickerPresented = false
                if let url { Task { await importFile(url) } }
            }
        }
    }
    // V3_PAIRING_PLACEMENT_STEPS_V1''', '''        .sheet(isPresented: $pickerPresented) {
            V3FilePicker(types: ["com.apple.property-list", "public.xml", "public.data"]) { url in
                pickerPresented = false
                if let url { Task { await importFile(url) } }
            }
        }
        .onAppear { receivedPairingFile = Self.oneReceivedPairingFile() }
    }
    // V3_PAIRING_PLACEMENT_STEPS_V1''', 'inbox appearance refresh')
    # Avoid repeated side effects from the same inbox file on an accidental
    # double tap. The existing backend validates before committing data.
    s=one(s, '''            message = ""
        } catch {
            // A failed import may have crossed the service mutation boundary.''', '''            message = ""
            receivedPairingFile = nil
            status.reload()
        } catch {
            // A failed import may have crossed the service mutation boundary.''','update after import')

    # At setup start, show one deterministic continuation rather than requiring
    # users to browse all the advanced sections. Uses all existing native
    # routes; does not create an independent authentication or VPN path.
    start='''    var body: some View {
        List {
            Section("Device") {'''
    extra='''    // SCARLET_V165_SINGLE_NEXT_ACTION: one primary next step. Reuse existing
    // SideStore operations, preserve confirmation and Apple system approval.
    private var nextAction: String {
        if setup.pairing.state == "actionRequired" || setup.pairing.state == "failed" { return "pairing" }
        if setup.account.state == "actionRequired" || setup.account.state == "failed" { return "account" }
        if setup.tunnel.state == "actionRequired" || setup.tunnel.state == "failed" { return "tunnel" }
        if V3JITLessCompletionPolicy.isRequired(osMajor: ProcessInfo.processInfo.operatingSystemVersion.majorVersion),
           V3JITLessPresentation.present(status.jitlessReadiness ?? .unknown).isOutstandingSetupTask {
            return "jitless"
        }
        if setup.verification.state != "complete" { return "verify" }
        return setup.isComplete(status: status) ? "complete" : "review"
    }
    var body: some View {
        List {
            Section("Continue Setup") {
                switch nextAction {
                case "pairing":
                    Text("Pairing is required. Existing records are reused; select a new one only if missing or rejected.")
                        .font(.footnote).foregroundColor(.secondary)
                    Button("Continue: Pairing", systemImage: "link") { showPairingSetup = true }
                        .accessibilityIdentifier("scarletV165ContinuePairing")
                case "account":
                    NavigationLink {
                        V3SignInView().environmentObject(status)
                    } label: { Label("Continue: Apple Account", systemImage: "person.crop.circle") }
                case "tunnel":
                    Button("Continue: Local VPN", systemImage: "network") { openLocalVPN() }
                        .disabled(vpnWorking)
                case "jitless":
                    Button("Continue: JIT-Less Setup", systemImage: "checkmark.shield") {
                        openCanonicalJITLessSetup()
                    }
                case "verify":
                    Button(setup.testRunning ? "Verifying…" : "Verify Installation", systemImage: "checkmark.seal") {
                        setup.runTestRefresh(status: status)
                    }
                    .disabled(setup.testRunning)
                case "review":
                    Label("Review remaining setup items below", systemImage: "list.bullet.clipboard")
                        .foregroundColor(.orange)
                default:
                    Label("Setup verified", systemImage: "checkmark.circle.fill")
                        .foregroundColor(.green)
                }
                Button("Re-check Existing Setup", systemImage: "arrow.clockwise") {
                    NSLog("[SCARLET_V165_FIRST_INSTALL] action=reload_confirmed")
                    Task { await setup.reloadAndRecalculate(status: status) }
                }
                .disabled(setup.testRunning)
                .font(.caption)
            }
            Section("Device") {'''
    part=s.index('struct V3SetupAssistantView: View {')
    pre,setup=s[:part],s[part:]
    setup=one(setup,start,extra,'single setup action')
    return pre+setup


def apply(root):
    p=root/SWIFT
    if not p.is_file() or p.is_symlink():raise ValueError('V165 generated V3 shell missing')
    s=p.read_text(encoding='utf-8')
    out=patch(s)
    if patch(out)!=out:raise ValueError('V165 patch not idempotent')
    if s!=out:p.write_text(out,encoding='utf-8')
    print('[PASS] V165 initial setup: one next step, file reuse, advanced legacy steps collapsed')

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: patch_v165_first_install_flow.py <LiveContainer>')
    apply(Path(sys.argv[1]))
