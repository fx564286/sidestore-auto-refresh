"""Fail-closed, source-audited anti-repeat gate for future Scarlet fixes.

Run before editing with --proposal JSON; CI runs without --proposal via unittest.
The baseline L001-L047 is immutable history. This check cannot infer causal
equivalence from arbitrary source code; explicit mechanism aliases and a
reviewed causal explanation are still required.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HISTORY = Path(__file__).with_name("scarlet_remediation_history.json")
FIRST_GATED_ID = 48
FAILURE_STATES = {
    "device_unresolved", "diagnostic_failure", "rollback",
    "device_partial_pass", "unverified", "diagnostic_only",
    "source_only", "ci_pending", "source_committed_static_and_xcode_ci_pending",
}
ALIASES = {
    "safe_area": {"safe_area", "remote_safearea", "safearea_cache", "fbscene_safe_insets"},
    "uiwindow_owner": {"uiwindow_owner", "hosting_owner", "root_controller_owner"},
    "statusbar_metrics": {"statusbar_metrics", "statusbar_frame", "statusbar_height"},
    "launch_policy": {"launch_policy", "scene_manifest", "bundle_policy"},
    "startup_order": {"startup_order", "deferred_xpc", "xpc_boot_order"},
    "guest_uikit_geometry": {"guest_uikit_geometry", "guest_window_offsets"},
    "overlay_hit_test": {"overlay_hit_test", "outside_shield"},
    "layout_timing": {"layout_timing", "deferred_layout", "ready_reveal"},
    "frame_transform": {"frame_transform", "viewport_rescale"},
    "dyld_guest_sdk_compatibility": {
        "dyld_guest_sdk_compatibility", "guest_macho_sdk_contract", "dyld_sdk_query"
    },
}
ALIASES = {alias: family for family, aliases in ALIASES.items() for alias in aliases}


def _mechanism(value: str) -> str:
    key = re.sub(r"[^a-z0-9_]+", "_", str(value).strip().lower())
    return ALIASES.get(key, key)


def _problem_family(value: str) -> str:
    # Different symptom labels do not make the same guest launch/layout
    # mechanism a new fix. R6P9 was classified guest_boot, but later
    # attempts target its visible symptom guest_top.
    if value in {"guest_top", "rotation_top", "guest_boot"}:
        return "resident_guest_surface"
    return value


def _code_signature(change: dict) -> tuple:
    def canonical(parts: list) -> str:
        # Comments and formatting alone are not a new implementation.
        return re.sub(r"\s+", "", "\n".join(
            line for line in parts if not line.lstrip().startswith(("//", "#"))
        ))
    return (change.get("file"), canonical(change.get("before", [])),
            canonical(change.get("after", [])))


def _entry_number(entry: dict) -> int:
    match = re.fullmatch(r"L(\d{3,})", str(entry.get("id", "")))
    if not match:
        raise ValueError(f"Invalid remediation ID: {entry.get('id')!r}")
    return int(match.group(1))


def check_candidate(candidate: dict, prior: list[dict]) -> list[str]:
    errors = []
    ident = candidate.get("id", "PROPOSAL")
    problem = candidate.get("problem", "")
    mech = _mechanism(candidate.get("mechanism", ""))
    novelty = candidate.get("novelty") or {}
    previous = [e for e in prior if _problem_family(e.get("problem", ""))
                == _problem_family(problem)]
    conflicts = [e for e in previous if _mechanism(e.get("mechanism", "")) == mech
                 and (e.get("status") in FAILURE_STATES
                      or e.get("device_verification")
                      != "device_visual_and_touch_pass")]
    if len(novelty.get("causal_difference", "")) < 40:
        errors.append(f"{ident}: missing concrete causal_difference (>=40 chars)")
    if len(novelty.get("falsifiable_prediction", "")) < 35:
        errors.append(f"{ident}: missing falsifiable_prediction (>=35 chars)")
    if not novelty.get("prior_excluded_ids"):
        errors.append(f"{ident}: must name previously excluded attempt IDs")
    else:
        known = {e.get("id") for e in prior}
        unknown = set(novelty["prior_excluded_ids"]) - known
        if unknown:
            errors.append(f"{ident}: unknown excluded attempt IDs {sorted(unknown)}")
    # The same failed mechanism is barred unless the proposal supplies an
    # actual new device observation and a falsifiable differentiation.
    if conflicts:
        evidence = novelty.get("new_device_evidence") or {}
        matching = {e["id"] for e in conflicts}
        if not matching.issubset(set(novelty.get("prior_excluded_ids", []))):
            errors.append(f"{ident}: repeated {mech} omits prior failures {sorted(matching)}")
        if not (evidence.get("source_commit") and evidence.get("event") and
                evidence.get("observed_value") and
                len(novelty.get("why_prior_fix_failed", "")) >= 40):
            errors.append(f"{ident}: BLOCK repeated mechanism {mech}; "
                          "requires new device source_commit/event/value and "
                          "specific explanation why prior code failed")
    if not candidate.get("code_locations"):
        errors.append(f"{ident}: candidate must contain proposed file/diff context")
    # Also block an identical source patch even if renamed to a new mechanism.
    prior_patches = {
        _code_signature(loc)
        for e in prior for loc in e.get("code_locations", [])
    }
    for change in candidate.get("code_locations", []):
        signature = _code_signature(change)
        if signature in prior_patches:
            errors.append(f"{ident}: duplicate source change {change.get('file')}")
        if not change.get("location", "").startswith("@@ "):
            errors.append(f"{ident}: missing unified diff location")
        if not (change.get("before") or change.get("after")):
            errors.append(f"{ident}: missing before/after source")
    return errors


def validate(history: dict, proposal: dict | None = None) -> list[str]:
    entries = history.get("entries", [])
    errors = []
    seen = set()
    for index, entry in enumerate(entries):
        try:
            n = _entry_number(entry)
        except ValueError as ex:
            errors.append(str(ex))
            continue
        if n in seen:
            errors.append(f"Duplicate remediation ID L{n:03d}")
        seen.add(n)
        # Protect the entire frozen history against silent deletion.
        if n != index + 1:
            errors.append(f"History sequence missing/reordered: L{n:03d}")
        if n >= FIRST_GATED_ID:
            errors.extend(check_candidate(entry, entries[:index]))
            if entry.get("source_verification") != "git_patch_observed":
                errors.append(f"L{n:03d}: new fix requires source-verified code diff")
            if not entry.get("source_revisions"):
                errors.append(f"L{n:03d}: source revisions missing")
            if not entry.get("code_locations"):
                errors.append(f"L{n:03d}: code locations missing")
    if len(entries) < FIRST_GATED_ID - 1:
        errors.append("Historical attempts L001-L047 missing")
    if proposal is not None:
        errors.extend(check_candidate(proposal, entries))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--history", type=Path, default=HISTORY)
    parser.add_argument("--proposal", type=Path,
                        help="Pre-edit proposal. Reject duplicate causal mechanisms.")
    args = parser.parse_args(argv)
    data = json.loads(args.history.read_text(encoding="utf-8"))
    proposal = (json.loads(args.proposal.read_text(encoding="utf-8"))
                if args.proposal else None)
    issues = validate(data, proposal)
    if issues:
        for issue in issues:
            print("[NO-REPEAT-BLOCK] " + issue, file=sys.stderr)
        return 2
    print(f"[NO-REPEAT-PASS] {len(data['entries'])} historical attempts reviewed; "
          "candidate source/causal duplicate guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
