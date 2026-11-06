#!/usr/bin/env python3
"""Evidence-based Scarlet Crystal release readiness, not a marketing pass.

A standalone SwiftUI typecheck, mock simulator screenshot or static Figma
source check NEVER certifies original native Liquid Glass, pairing or install.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]

def assess(root:Path)->dict:
    manifest=json.loads((root/"rebuild/design/figma-measured-baseline.json").read_text())
    ui=(root/"rebuild/Sources/ScarletIndependentUI/ScarletIndependentShell.swift").read_text()
    audit_path=root/"rebuild/Sources/ScarletCleanCore/ScarletControlAuditTrail.swift"
    host=root/"rebuild/HostApp"
    host_files=list(host.rglob("*")) if host.exists() else []
    host_source="\n".join(p.read_text(errors="replace")
                          for p in host_files if p.is_file() and p.suffix in (".swift",".m",".mm"))
    checks=[]
    def add(id:str,status:str,why:str,release_required=True):
        checks.append(dict(id=id,status=status,evidence=why,releaseRequired=release_required))
    six=len(manifest["screens"])==6
    add("figma_layer_baseline","passed" if six else "failed",
        "Six actual editable Figma screen IDs and measured geometry recorded; no live change webhook configured",
        False)
    anchors=all((s["codeSection"] is None or s["codeSection"] in ui)
                for s in manifest["screens"])
    add("figma_to_swiftui_source_parity","passed" if anchors else "failed",
        "Named screen sections mapped; typecheck and static text test required. Pixel-by-pixel renderer comparison outstanding",
        False)
    add("independent_control_audit","implemented_not_connected" if audit_path.exists()
        else "blocked",
        "Privacy-safe bounded action receipt actor exists; no real Scarlet host invokes or exports it yet")
    native="UIGlassEffect" in host_source and "isInteractive" in host_source
    add("original_native_liquid_glass","blocked" if not native else "source_present_device_unverified",
        "No verifiable original native UIGlassEffect host/gesture integration in new HostApp source"
        if not native else "Source references UIGlassEffect; original-runtime checksum and physical gesture verification still required")
    ui_host=any(p.name.endswith("App.swift") for p in host_files if p.is_file())
    add("livecontainer_host_integration","blocked" if not ui_host else "source_present_device_unverified",
        "Only isolated SwiftUI exists; real LiveContainer host app entrypoint missing"
        if not ui_host else "Host entrypoint present; guest runtime device tests outstanding")
    add("native_glass_tab_and_switcher","blocked",
        "Binding<Tab> and AnyView injection types are present, but no original working glass view instances have been provided by the iOS host")
    add("window_manager_gestures","blocked",
        "Figma has recent apps/window manager overlay, but no bound native overlay for long press, outside tap or rotation in new host")
    add("apple_login_pairing_2fa","blocked",
        "Live iPhone SideStore/SideSign authentication and six-digit 2FA have not been reproduced on the rebuilt application")
    add("seven_day_refresh_and_install","blocked",
        "Policy code exists; free profile renewal requires Apple authentication, signing and verified same-bundle iPhone reinstall")
    add("real_device_visual_regression","blocked",
        "No paired iPhone run with portrait/landscape screenshots, touch hit tests and original Liquid Glass optics")
    add("signed_ipa_and_user_data","blocked",
        "No new four-bundle signed IPA, entitlement comparison, in-place installation, or verified data preservation")
    blockers=[x["id"] for x in checks if x["releaseRequired"] and x["status"]!="passed"]
    return {
        "schema":1,
        "generatedAt":datetime.now(timezone.utc).isoformat(),
        "project":"Scarlet Crystal clean rebuild",
        "figmaFileKey":manifest["source"]["fileKey"],
        "visualScreenCount":len(manifest["screens"]),
        "checks":checks,
        "releaseReady":not blockers,
        "blockingChecks":blockers,
        "simulatorEvidenceIsNotNativeGlass":True,
        "currentStatus":"BLOCKED" if blockers else "READY_FOR_DEVICE_RELEASE_REVIEW",
        "caveat":"Only a real signed app on the actual iPhone can establish native Liquid Glass and install correctness."
    }

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,default=ROOT/"rebuild/reports/live-readiness.json")
    p.add_argument("--enforce-release",action="store_true")
    a=p.parse_args()
    report=assess(ROOT)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("[SCARLET_READINESS]",report["currentStatus"])
    for x in report["checks"]:
        print(f"[{x['status']}] {x['id']}: {x['evidence']}")
    print("[REPORT]",a.output)
    return 2 if a.enforce_release and not report["releaseReady"] else 0

if __name__=="__main__":sys.exit(main())
