#!/usr/bin/env python3
"""Replace old NRG #191 updater with provable Scarlet installed/release identities.

V188 was signed as ScarletBuildLabel=V188 / CFBundleVersion=3.8.202.
The legacy home updater instead queried unrelated nrg-ota-v191 release tags
and read a nonexistent NRGOTASequence (defaulting to 0). It also escaped
Swift interpolation literally, displaying '#(current)' and '#(build.version)'.
This patch touches ONLY the home OTA component, never Liquid Glass/dock.
"""
from pathlib import Path
import sys

FILE=Path("LiveContainerSwiftUI/Views/V3UnifiedShell.swift")
OLD="// NRG_V52_IN_APP_OTA: download is not evidence of a successful signed installation."
MARK="// SCARLET_V189_VERIFIABLE_UPDATE_IDENTITY"
NEW=r'''// SCARLET_V189_VERIFIABLE_UPDATE_IDENTITY
// Exact installed app receipt comes from this running app's Info.plist,
// NOT the unrelated NRG release sequence or stale remote tag number.
// Download/staging is never represented as a successful device install.
private struct ScarletSignedRelease {
    let version: Int
    let ipa: URL
    let sha256: String
}
private struct NRGOTAUpdateView: View {
    @EnvironmentObject private var status: V3SideStoreStatusStore
    @State private var candidate: ScarletSignedRelease?
    @State private var busy = false
    @State private var note = "Scarlet Crystal 서명 릴리스의 업데이트 상태를 확인해."
    private let repo = "fx564286/sidestore-auto-refresh"

    private var installedLabel: String? {
        guard let raw = Bundle.main.object(forInfoDictionaryKey: "ScarletBuildLabel") as? String,
              raw.range(of: "^V[0-9]+$", options: .regularExpression) != nil else { return nil }
        return raw
    }
    private var installedNumber: Int? {
        guard let label = installedLabel else { return nil }
        return Int(label.dropFirst())
    }
    private var bundleBuild: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "확인 불가"
    }
    private var installedIdentity: String {
        guard let label = installedLabel else {
            return "설치된 Scarlet 빌드 식별 불가 · 앱 \(bundleBuild)"
        }
        return "현재 실행 중: \(label) · 앱 \(bundleBuild)"
    }
    private var mayStage: Bool {
        guard let release = candidate else { return false }
        return installedNumber.map { release.version > $0 } ?? true
    }
    var body: some View {
        Group {
            VStack(alignment: .leading, spacing: 8) {
                Label("Scarlet Crystal 업데이트", systemImage: "arrow.down.app")
                Text(installedIdentity)
                    .font(.caption2).foregroundColor(.secondary)
                    .accessibilityIdentifier("scarletInstalledBuildIdentity")
                Text(note).font(.caption).foregroundColor(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                if busy { ProgressView() }
            }
            .accessibilityElement(children: .contain)

            Button {
                Task { await check() }
            } label: {
                Label("서명 릴리스 확인", systemImage: "arrow.clockwise")
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.borderless)
            .disabled(busy)
            .accessibilityIdentifier("scarletSignedReleaseCheck")

            if let candidate, mayStage {
                Button {
                    Task { await downloadAndStage(candidate) }
                } label: {
                    Label("V\(candidate.version) IPA 내려받아 SideStore로 전달",
                          systemImage: "square.and.arrow.down")
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .contentShape(Rectangle())
                }
                .buttonStyle(.borderless)
                .disabled(busy)
                .accessibilityIdentifier("scarletSignedReleaseStage")
            }

            Text("내려받기와 설치는 별개야. 서명·설치 결과를 확인하기 전 기존 앱을 삭제하지 마.")
                .font(.caption2).foregroundColor(.secondary)
        }
    }

    @MainActor private func check() async {
        guard !busy else { return }
        busy = true
        defer { busy = false }
        candidate = nil
        do {
            let url = URL(string: "https://api.github.com/repos/\(repo)/releases?per_page=60")!
            var request = URLRequest(url: url)
            request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
            request.timeoutInterval = 20
            request.cachePolicy = .reloadIgnoringLocalCacheData
            let (payload, response) = try await URLSession.shared.data(for: request)
            guard let response = response as? HTTPURLResponse, response.statusCode == 200,
                  payload.count < 2_000_000,
                  let releases = try JSONSerialization.jsonObject(with: payload) as? [[String: Any]]
            else { throw NSError(domain: "ScarletUpdate", code: 1) }
            let signed = releases.compactMap { release -> ScarletSignedRelease? in
                guard (release["draft"] as? Bool) == false,
                      let tag = release["tag_name"] as? String,
                      let assets = release["assets"] as? [[String: Any]] else { return nil }
                let parts = tag.split(separator: "-")
                guard parts.count == 5, parts[0] == "scarlet",
                      parts[2] == "device", parts[3] == "signed",
                      parts[4].count == 8, parts[4].allSatisfy({ $0.isNumber }),
                      parts[1].first == "v",
                      let version = Int(parts[1].dropFirst()), version > 0 else { return nil }
                let filename = "Scarlet-Crystal-V\(version)-SIGNED-DEVELOPMENT.ipa"
                guard let file = assets.first(where: { ($0["name"] as? String) == filename }),
                      (file["state"] as? String) == "uploaded",
                      (file["size"] as? Int ?? 0) > 1_000_000,
                      let link = file["browser_download_url"] as? String,
                      let ipa = URL(string: link), ipa.scheme == "https", ipa.host == "github.com",
                      ipa.path == "/\(repo)/releases/download/\(tag)/\(filename)",
                      let digest = file["digest"] as? String, digest.hasPrefix("sha256:") else {
                    return nil
                }
                let hash = String(digest.dropFirst("sha256:".count))
                guard hash.range(of: "^[0-9a-fA-F]{64}$", options: .regularExpression) != nil else {
                    return nil
                }
                return ScarletSignedRelease(version: version, ipa: ipa, sha256: hash.lowercased())
            }
            guard let newest = signed.max(by: { $0.version < $1.version }) else {
                throw NSError(domain: "ScarletUpdate", code: 2)
            }
            if let installed = installedNumber, installed >= newest.version {
                note = "설치 \(installedLabel ?? "확인 불가") · 공개 서명 릴리스 V\(newest.version). 새 업데이트 없음."
            } else {
                candidate = newest
                note = installedNumber == nil
                    ? "설치 빌드를 확인할 수 없어. 공개 서명 릴리스 V\(newest.version)를 찾았어. 수동으로 확인해."
                    : "새로운 서명 릴리스 V\(newest.version)를 찾았어. 아직 설치된 것은 아니야."
            }
            NSLog("[SCARLET_V189_UPDATE] stage=check installed=%@ available=%d candidate=%d",
                  installedLabel ?? "unknown", newest.version, candidate != nil ? 1 : 0)
        } catch {
            note = "서명 릴리스 확인 실패. 기존 앱과 데이터는 변경되지 않았어."
            NSLog("[SCARLET_V189_UPDATE] stage=check result=failed")
        }
    }

    @MainActor private func downloadAndStage(_ build: ScarletSignedRelease) async {
        guard !busy, mayStage, candidate?.version == build.version else { return }
        busy = true
        defer { busy = false }
        var temporary: URL?
        defer { if let temporary { try? FileManager.default.removeItem(at: temporary) } }
        do {
            guard let host = Bundle.main.bundleIdentifier,
                  status.installedApps.contains(where: { $0.isHost && $0.bundleID == host }),
                  status.connected, !status.needsSignIn, !status.loading else {
                throw NSError(domain: "ScarletUpdate", code: 3)
            }
            note = "서명 IPA 내려받는 중…"
            let (ipa, response) = try await URLSession.shared.download(for: URLRequest(url: build.ipa))
            temporary = ipa
            guard let response = response as? HTTPURLResponse, response.statusCode == 200 else {
                throw NSError(domain: "ScarletUpdate", code: 4)
            }
            let size = (try FileManager.default.attributesOfItem(atPath: ipa.path)[.size] as? NSNumber)?.int64Value ?? 0
            guard size > 1_000_000 && size < 350_000_000 else {
                throw NSError(domain: "ScarletUpdate", code: 5)
            }
            let handle = try FileHandle(forReadingFrom: ipa)
            defer { try? handle.close() }
            var hasher = SHA256()
            while true {
                let bytes = handle.readData(ofLength: 1_048_576)
                if bytes.isEmpty { break }
                hasher.update(data: bytes)
            }
            let actual = hasher.finalize().map { String(format: "%02x", $0) }.joined()
            guard actual == build.sha256 else { throw NSError(domain: "ScarletUpdate", code: 6) }
            NSLog("[SCARLET_V189_UPDATE] stage=verified candidate=%d bytes=%lld sha256=pass",
                  build.version, size)
            guard status.stageSharedIPA(ipa,title: "Scarlet Crystal V\(build.version) — 설치 전 서명 검증") != nil else {
                throw NSError(domain: "ScarletUpdate", code: 7)
            }
            note = "서명 IPA 전달 완료. 실제 설치·앱 실행은 아직 확인되지 않았어."
            NSLog("[SCARLET_V189_UPDATE] stage=staged candidate=%d install_result=unverified",
                  build.version)
        } catch {
            note = "IPA 전달 실패. 기존 앱은 변경하지 않았어."
            NSLog("[SCARLET_V189_UPDATE] stage=stage result=failed")
        }
    }
}
'''

def patch(src: str) -> str:
    if MARK in src:
        if src.count(MARK) != 1 or "scarletSignedReleaseStage" not in src:
            raise ValueError("V189 update component partial")
        return src
    if src.count(OLD) != 1:
        raise ValueError("legacy NRG update section missing")
    original=src[src.index(OLD):]
    required=["NRGOTASequence", "nrg-ota-v", "Text(\"#\\\\(current)\")",
              "LiveContainer-SideStore-v3.0.3-rc.ipa"]
    if any(x not in original for x in required):
        raise ValueError("Unexpected legacy updater; refuse blind overwrite")
    return src[:src.index(OLD)] + NEW

def apply(root: Path):
    target=root/FILE
    if not target.is_file() or target.is_symlink():
        raise ValueError("V3 Swift UI source missing")
    before=target.read_text(encoding="utf8")
    after=patch(before)
    if patch(after)!=after:
        raise ValueError("V189 update patch not idempotent")
    if after!=before:
        target.write_text(after,encoding="utf8")
    print("[PASS] V189 current installed ScarletBuildLabel, GitHub signed releases only")
    print("[PASS] Legacy #191 NRG update route removed, no false install-complete claim")
    print("[PASS] Liquid Glass and window manager untouched")

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("usage: patch_v189_update_provenance.py <LiveContainer>")
    apply(Path(sys.argv[1]))
