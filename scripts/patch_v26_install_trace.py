#!/usr/bin/env python3
"""NRG V26: capture cancellation provenance and the *actual* failed pipeline step.

Only fixed enums, booleans and allowlisted NSError domains are logged. Never
log IPA URLs, credentials, certificates, app titles, bundle IDs, or userInfo.
This is instrumentation, NOT automatic reinstallation or cancellation bypass.
"""
from pathlib import Path
import sys

MARKER="NRG_V26_CANCEL_ORIGIN"

def replace_once(content, old, new, filename):
    count=content.count(old)
    if count != 1:
        raise SystemExit(f"[FAIL] {filename}: expected 1 pinned anchor, found {count}")
    return content.replace(old,new,1)

def patch(root: Path):
    exe=root/"SideStore/Core/Operations/PipelineExecutor.swift"
    runner=root/"SideStore/Core/Operations/PipelineRunner.swift"
    downloader=root/"SideStore/Core/Operations/StandaloneOperations/DownloadAppOperation.swift"
    for f in (exe,runner,downloader):
        if not f.is_file():raise SystemExit(f"[FAIL] missing: {f}")
    texts={p:p.read_text(encoding="utf-8") for p in (exe,runner,downloader)}
    if all(MARKER in texts[p] for p in texts):
        print("[PASS] NRG V26 cancellation instrumentation already applied")
        return
    if any(MARKER in texts[p] for p in texts):
        raise SystemExit("[FAIL] partial V26 patch found; no partial rewrite")

    # The upstream deferred per-step logger is disabled by default. Log a
    # sanitized failure marker unconditionally, before the error is mapped.
    old="""        } catch {
            result = error
            throw error
        }
    }
    
    private func logOperationResult"""
    new="""        } catch {
            // NRG_V26_CANCEL_ORIGIN — backend source step, no URL or user data.
            let native = error as NSError
            let domain = [NSURLErrorDomain, NSPOSIXErrorDomain, NSCocoaErrorDomain,
                          "ALTErrorDomain", "ALTServerErrorDomain",
                          "InstallationProxyErrorDomain"].contains(native.domain)
                ? native.domain : "redacted"
            debugLog("[NRG_V26_PIPELINE_STEP] step=\\(step) task_cancelled=\\(Task.isCancelled) domain=\\(domain) code=\\(native.code)")
            result = error
            throw error
        }
    }

    private func logOperationResult"""
    texts[exe]=replace_once(texts[exe],old,new,exe.name)
    old="""            let elapsed = CFAbsoluteTimeGetCurrent() - group.context.operationStartTime
            let status = Task.isCancelled ? "CANCELLED" : "FAILED"
            if Task.isCancelled {"""
    new="""            let elapsed = CFAbsoluteTimeGetCurrent() - group.context.operationStartTime
            // NRG_V26_CANCEL_ORIGIN: a CANCELLED summary means Task was
            // cancelled, not necessarily that the user pressed Cancel.
            let native = error as NSError
            let safeDomain = [NSURLErrorDomain, NSPOSIXErrorDomain,
                              NSCocoaErrorDomain, "ALTErrorDomain",
                              "ALTServerErrorDomain"].contains(native.domain)
                ? native.domain : "redacted"
            debugLog("[NRG_V26_PARENT_TASK] task_cancelled=\\(Task.isCancelled) group_cancelled=\\(group.progress.isCancelled) step_progress_cancelled=\\(progress.progress(for: operation)?.isCancelled ?? false) domain=\\(safeDomain) code=\\(native.code)")
            let status = Task.isCancelled ? "CANCELLED" : "FAILED"
            if Task.isCancelled {"""
    texts[runner]=replace_once(texts[runner],old,new,runner.name)
    old="""            return try await self.download(appVersion ?? app)
            
        } catch let error as VerificationError where error.code == .iOSVersionNotSupported {"""
    new="""            do {
                return try await self.download(appVersion ?? app)
            } catch {
                // NRG_V26_CANCEL_ORIGIN: distinguishes download errors from
                // parent Task cancellation, without revealing the source URL.
                let native = error as NSError
                let safeDomain = [NSURLErrorDomain, NSPOSIXErrorDomain,
                                  NSCocoaErrorDomain, "ALTErrorDomain",
                                  "ALTServerErrorDomain"].contains(native.domain)
                    ? native.domain : "redacted"
                debugLog("[NRG_V26_DOWNLOAD_TERMINAL] task_cancelled=\\(Task.isCancelled) operation_cancelled=\\(self.isCancelled) domain=\\(safeDomain) code=\\(native.code)")
                throw error
            }

        } catch let error as VerificationError where error.code == .iOSVersionNotSupported {"""
    texts[downloader]=replace_once(texts[downloader],old,new,downloader.name)
    if "NRG_V24_INSTALL_DOWNLOAD_RECOVERY" not in texts[downloader]:
        raise SystemExit("[FAIL] original bounded retry would be lost")
    for f,t in texts.items():
        if t.count("NRG_V26_CANCEL_ORIGIN") != 1:
            raise SystemExit(f"[FAIL] missing or duplicate marker in {f.name}")
    for f,t in texts.items():f.write_text(t,encoding="utf-8")
    print("[PASS] V26: pipeline source-step, parent cancellation, downloader error provenance")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v26_install_trace.py <embedded-sidestore>")
    patch(Path(sys.argv[1]))
