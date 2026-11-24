"""P84 strict strategy-family gate. Applies to NEW proposals / L140+ only.

The L001-L139 evidence archive is immutable: historical failures are evidence,
not silently reinterpreted as passing the new contract. A renamed file,
function, sample timer or a new iPhone log cannot waive a repeated method.
This is a conservative source policy; it cannot mathematically prove arbitrary
programs are semantically distinct. The mandatory native/device proofs remain.
"""
from __future__ import annotations

import re

# These are ACTUAL attempted *effects*, not 139 distinct fixes. A single
# historical attempt may touch more than one effect family. IDs deliberately
# refer to the immutable existing ledger, rather than inventing old diffs.
BLOCKED_ISLAND_METHODS = {
    "safe_area_recalibration": ("L003", "L028", "L032", "L035", "L050", "L071", "L074"),
    "native_statusbar_visibility_or_style": ("L092", "L094", "L096", "L123", "L131", "L138"),
    "header_position_or_constraint": ("L081", "L083", "L088", "L098", "L100", "L101", "L135"),
    "scroll_inset_offset_or_viewport": ("L063", "L071", "L072", "L074", "L102", "L110", "L111", "L112", "L113", "L125", "L127"),
    "host_fbscene_crop_resize_or_transform": ("L005", "L010", "L021", "L084", "L085", "L087", "L093", "L095"),
    "retiming_delayed_reprobe_or_retry": ("L013", "L014", "L076", "L091", "L123"),
    "overlay_chrome_or_uiwindow_mask": ("L002", "L004", "L006", "L016", "L017", "L084"),
    "parent_layout_hook_or_reflow": ("L082", "L100", "L101", "L102", "L106", "L110", "L111", "L112"),
}

# A strategy must name an auditable causal contract, NOT an invented synonym.
# Candidates still need to establish genuine newness against every full diff.
POTENTIALLY_DISTINCT_ISLAND_METHODS = {
    "original_vs_resident_creation_path_repair",
    "guest_render_attachment_contract_repair",
    "guest_original_layout_writer_root_cause_repair",
    "native_process_scene_ownership_contract_repair",
}
OTHER_ALLOWED_METHODS = {
    "user_confirmed_native_resident_ownership_drain_before_classic_bootstrap",
    "typed_sidesign_certificate_quota_error_contract",
    "owner_scoped_refresh_requested_returned_target_set_coverage",
    "host_refresh_profile_readback_transaction_lease",
    # Simulator evidence only: bind live process identity across screenshot capture.
    "simulator_launch_pid_bundle_liveness_before_after_capture",
    "worker_verified_update_snapshot_and_preportal_existing_identity_pin",
    "native_shortcut_verified_release_self_update_and_signed_identity_fence",
    "cumulative_binary_release_identity_and_native_readiness_serialization",
    "classic_bootstrap_owned_switcher_and_token_bound_diagnostic_handoff",
    "interactive_account_priority_and_certificate_transport_reservation",
    # R6P129: align native slot wire limits, result semantics and readback lifetime.
    "native_slot_response_contract_and_serialized_readback",
    # R6P128: exact installed bundle artwork and truthful read-only ownership labels.
    "exact_installed_bundle_artwork_and_independent_management_state",
    "paired_installation_proxy_inventory_and_unverified_renewal_cooldown",
    "source_history_strict_strategy_gate",
    "independent_guest_import_transaction_repair",
    "account_auth_team_selection_repair",
    "host_origin_verified_xpc_bundle_authority",
    "native_settings_account_group_divider_owner",
    # P92 restores a removed native JIT-less route and separates guest-local
    # signing eligibility from stronger SideStore device refresh eligibility.
    "original_jitless_diag_navigation_guest_scoped_recovery",
    # P94: explicit selected-account P12 (validated by host profile DER) is
    # bridged to original LC guest signer only via reversible kernel check.
    "user_approved_account_p12_to_lc_signed_host_verified_bridge",
    # P99: two independently built P98 sources shared a CFBundleVersion,
    # making it impossible for one published IPA to contain both repairs.
    "release_branch_convergence_unique_build_identity",
    "xpc_auth_guest_lifecycle_rebind_after_confirmed_disconnect",
    # P107: preserve bounded native worker outcomes through the existing XPC
    # response state machine; this is not a new signing or layout method.
    "explicit_p12_import_owned_host_resign_transaction",
    "native_host_resign_exact_owner_signer_transaction_pin",
    "native_build_public_ipa_release_job_branch_gate_repair",
    "original_jitless_native_form_top_scroll_edge_restore",
    "deterministic_original_jitless_fixture_in_native_ci",
    "native_refresh_xpc_result_fidelity",
    "strict_x509_host_profile_stale_signer_bridge_replacement",
    "diagnostic_explicit_consent_public_link_transport",
    "diagnostic_user_approved_one_tap_link_sharing",
    "native_refresh_host_signer_owner_mismatch_exact_reason",
    "native_objc_arc_fixture_property_name_repair",
    # P195: diagnose simulator-target compilation independently of hosted macOS
    # CoreSimulator boot availability; retain explicit stage-specific evidence.
    "simulator_diagnostic_compile_first_runtime_stage_isolation",
    # P196: upstream LiveContainer uses ARM64-only svc assembler instructions;
    # constrain only the separate simulator diagnostic target architecture.
    "simulator_arm64_only_architecture_routing_for_upstream_arm_asm",
    # R6P122: show two existing, independently owned app registries without
    # migrating installed bundles or changing the native signing/refresh path.
    "owner_scoped_sidestore_catalog_separate_from_lc_guest_presentation",
    # R6P124: gate AVAudioSession activation within paused guest LiveProcess only.
    "guest_local_active_session_activation_fence",
    # R6P124 native compiler: project-owned NSErrorDomain for synthetic audio block.
    "guest_audio_sdk_compatible_custom_nserror_domain",
    # R6P123: source-backed managed catalog copy is not an IPA install-outcome verdict.
    "source_scoped_device_catalog_copy_without_install_result_projection",
    # R6P126: same launcher artwork/grid with separate LC and SideStore actions.
    "owner_scoped_launcher_visual_design_parity",
    # R6P126: allow current layout branch to produce a distinct unsigned IPA.
    "native_launcher_qa_branch_build_identity_release_binding",
}

# This catches a candidate that claims a novel family but still ADDS the same
# known symptom masking. Inspect *new* lines, not removed historical code.
KNOWN_MASKING_OPERATIONS = {
    "safe_area_recalibration": re.compile(r"additionalSafeAreaInsets|safeAreaInsets\s*=|safeAreaInsetsPortrait|safeAreaEdgeInsets|safeAreaLayoutGuide\s*\.", re.I),
    "native_statusbar_visibility_or_style": re.compile(r"\.statusBarHidden\s*\(|prefersStatusBarHidden\s*[:=]|setStatusBarHidden\s*\(|statusBarStyle\s*=", re.I),
    "header_position_or_constraint": re.compile(r"\bheader\.(?:frame|transform|center)\s*=|header\.topAnchor|header\.origin\s*=", re.I),
    "scroll_inset_offset_or_viewport": re.compile(r"(?:scroll|sc)\.(?:contentInset|contentOffset|frame)\s*=|scroll\.adjustedContentInset\s*=", re.I),
    "host_fbscene_crop_resize_or_transform": re.compile(r"(?:remoteWindow|fbscene|guestScene|hostWindow)\.(?:frame|transform|bounds)\s*=", re.I),
}


def _clean(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", str(text).strip().lower()).strip("_")


def check_distinct_method(candidate: dict, previous: list[dict]) -> list[str]:
    """Fail closed on same operational family even with additional device logs."""
    ident = str(candidate.get("id") or "PROPOSAL")
    errors: list[str] = []
    issue = _clean(candidate.get("incident_family", ""))
    method = _clean(candidate.get("strategy_family", ""))
    fingerprint = str(candidate.get("operation_fingerprint", "")).strip()
    if not issue:
        errors.append(f"{ident}: incident_family required for strict no-repeat")
    if not method:
        errors.append(f"{ident}: strategy_family required for strict no-repeat")
    if len(fingerprint) < 45:
        errors.append(f"{ident}: operation_fingerprint must describe exact source-level effect (>=45 chars)")
    if not candidate.get("source_behavior_contract") or len(str(candidate["source_behavior_contract"])) < 45:
        errors.append(f"{ident}: actual source_behavior_contract is mandatory")
    if not candidate.get("rollback_commit"):
        errors.append(f"{ident}: source rollback_commit required")
    same_issue = [p for p in previous if _clean(p.get("incident_family", "")) == issue]
    repeated = [p.get("id", "?") for p in same_issue
                if _clean(p.get("strategy_family", "")) == method and method]
    if repeated:
        errors.append(f"{ident}: HARD BLOCK same operational family '{method}' already used {repeated}; device evidence cannot waive")

    if issue == "island_content_collision":
        existing_ids = {p.get("id") for p in previous}
        if method in BLOCKED_ISLAND_METHODS:
            attempted = [p for p in BLOCKED_ISLAND_METHODS[method] if p in existing_ids]
            errors.append(f"{ident}: HARD BLOCK already-attempted island method '{method}' at {attempted}; renaming/timing/new evidence does not authorize reuse")
        elif method not in POTENTIALLY_DISTINCT_ISLAND_METHODS:
            errors.append(f"{ident}: unregistered island strategy '{method}' — cannot bypass using a fresh name")
        proof = candidate.get("normal_experimental_diff") or {}
        for key in ("normal_mode_source", "resident_mode_source", "proven_difference", "failure_causal_link"):
            if len(str(proof.get(key, ""))) < 25:
                errors.append(f"{ident}: normal_experimental_diff.{key} must cite actual source/observed distinction")
        alternatives = candidate.get("alternative_strategies") or []
        if len(alternatives) < 3 or len(set(str(a.get("strategy_family", "")) for a in alternatives)) < 3:
            errors.append(f"{ident}: compare three genuinely distinct strategies with previous attempt IDs")
        for a in alternatives:
            if not a.get("strategy_family") or not a.get("reason_not_selected"):
                errors.append(f"{ident}: each alternative needs family and reason_not_selected")
        if len(str(candidate.get("runtime_acceptance_gate", ""))) < 50:
            errors.append(f"{ident}: signed-device acceptance needs island/icons/scroll/touch/rotation and A-B-A")
        if len(str(candidate.get("new_source_root_cause", ""))) < 50:
            errors.append(f"{ident}: new_source_root_cause needs verified normal-vs-resident causal analysis")
        if not any(loc.get("file", "").startswith(("rebuild/HostApp/", "rebuild/integration/"))
                   for loc in candidate.get("code_locations", [])):
            errors.append(f"{ident}: island fix must change functional host/integration source, not only logs/tests")
        for loc in candidate.get("code_locations", []):
            for line in loc.get("after", []):
                stripped = str(line).strip()
                if stripped.startswith(("//", "#", "*")):
                    continue
                for family, pattern in KNOWN_MASKING_OPERATIONS.items():
                    if pattern.search(stripped):
                        errors.append(f"{ident}: HARD BLOCK new source uses old '{family}' operation in {loc.get('file')}")
    elif method not in OTHER_ALLOWED_METHODS and method not in POTENTIALLY_DISTINCT_ISLAND_METHODS:
        errors.append(f"{ident}: unregistered strategy_family '{method}' — reviewed taxonomy update required")
    return errors
