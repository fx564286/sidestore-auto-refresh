from __future__ import annotations

import ast
from pathlib import Path
import re
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "build-current.yml"
SCRIPTS = ROOT / "scripts"
REQUIRED_SCRIPTS = {
    "patch_jktcp_reliability.py",
    "patch_coredevice_idevice.py",
    "patch_sidestore_integration.py",
    "patch_background_automation.py",
    "patch_local_idevice_package.py",
    "adapt_sidestore_070_pairing.py",
    "adapt_sidestore_070_signing.py",
}
LIVE_CONTAINER_SCRIPTS = {
    "patch_lc_certificate_observation.py",
    "patch_livecontainer_autorefresh.py",
    "patch_embedded_sidestore_startup.py",
    "patch_v3_unified_shell.py",
    "patch_sidesign_2fa_state.py",
    "patch_v3_service.py",
    "patch_combined_refresh_contract.py",
    "patch_embedded_keychain.py",
    "patch_guest_return.py",
    "patch_multitask_dock.py",
    "patch_dead10cc_fix.py",
    "patch_combined_refresh_contract.py",
    "patch_combined_transport.py",
    "patch_combined_service_startup.py",
    "patch_refresh_result_bridge.py",
    "patch_app_layout.py",
    "patch_embedded_sidestore_startup.py",
    "patch_local_idevice_package.py",
    "patch_combined_service_startup.py",
    "combined_build_evidence.py",
    "run_issue25_rendering.py",
    "patch_app_layout.py",
    "audit_ipa_signing.py",
    "patch_guest_return.py",
    "patch_combined_transport.py",
    "patch_combined_service_startup.py",
    "patch_refresh_result_bridge.py",
    "patch_background_automation.py",
    "patch_combined_refresh_contract.py",
    "patch_embedded_sidestore_startup.py",
    "patch_local_idevice_package.py",
    "patch_v3_service.py",
    "patch_combined_service_startup.py",
    "combined_build_evidence.py",
    "run_issue25_rendering.py",
    "patch_app_layout.py",
    "package_livecontainer_combined.py",
    "audit_ipa_signing.py",
    "patch_guest_return.py",
    "patch_combined_transport.py",
    "patch_refresh_result_bridge.py",
    "patch_embedded_sidestore_startup.py",
    "patch_local_idevice_package.py",
}
LIVE_CONTAINER_SCRIPT = "patch_livecontainer_autorefresh.py"
LIVE_CONTAINER_STARTUP_SCRIPT = "patch_embedded_sidestore_startup.py"
COMBINED_REFRESH_SCRIPT = "patch_combined_refresh_contract.py"
EMBEDDED_KEYCHAIN_SCRIPT = "patch_embedded_keychain.py"
APP_LAYOUT_SCRIPT = "patch_app_layout.py"
V3_UNIFIED_SHELL_SCRIPT = "patch_v3_unified_shell.py"

_SENSITIVE_ARTIFACT_SUFFIXES = {".p12", ".pfx", ".der", ".pem", ".key"}
_SENSITIVE_NAMES = re.compile(
    r"(?i)(pairingfile|rppairing|client_(cert|key)|lockdowndirectdiag|"
    r"(?:^|[/_.-])pairing(?:[/_.-]|$))"
)
_PUBLIC_SOURCE_DIRS = {"scripts", "tests", "docs"}
_PUBLIC_SOURCE_SUFFIXES = {
    ".c", ".cpp", ".h", ".hpp", ".js", ".md", ".rst", ".py", ".rs", ".swift", ".ts", ".tsx"
}


def _is_sensitive_reachable_path(path: str) -> bool:
    """Classify Git path output without treating source identifiers as secrets."""
    normalized = path.replace("\\", "/").strip("/")
    if not normalized:
        return False
    parts = normalized.split("/")
    basename = parts[-1].lower()
    suffix = Path(basename).suffix

    # These formats are private signing/pairing material wherever they occur.
    if suffix in _SENSITIVE_ARTIFACT_SUFFIXES:
        return True
    # Source identifiers may mention pairing. Serialized data (including JSON
    # and plist) and private material never inherit the source exemption.
    if _SENSITIVE_NAMES.search(normalized):
        is_public_source = (
            len(parts) > 1
            and parts[0].lower() in _PUBLIC_SOURCE_DIRS
            and suffix in _PUBLIC_SOURCE_SUFFIXES
        )
        return not is_public_source
    return False


class RepositoryTests(unittest.TestCase):
    def test_current_files_exist(self):
        self.assertTrue((ROOT / "README.md").is_file())
        self.assertTrue((ROOT / "LICENSE").is_file())
        self.assertTrue((ROOT / "CONTRIBUTING.md").is_file())
        self.assertTrue((ROOT / "docs" / "VERIFICATION.md").is_file())
        self.assertTrue((ROOT / "SECURITY.md").is_file())
        self.assertTrue(WORKFLOW.is_file())
        self.assertEqual(
            {path.name for path in SCRIPTS.glob("*.py")},
                REQUIRED_SCRIPTS | LIVE_CONTAINER_SCRIPTS | {
                    "patch_sidesign_privacy.py", "verify_candidate_ipa.py", "run_required_tests.py",
                    "patch_nrg_gsa_auth.py", "patch_nrg_gsa_http_v2.py",
                    "patch_nrg_gsa_client_v3.py", "patch_v24_install_download.py", "patch_v26_install_trace.py",
                    "patch_v27_guest_switch.py", "patch_v27_provisioning.py",
                    "patch_v28_refresh_regression.py", "patch_v28_guest_lifecycle.py", "patch_v28_pip_audio.py",
                    "patch_v31_adi_45061.py", "patch_v32_jitless_diagnosis.py",
                    "patch_v33_sidesign_memory.py", "patch_v33_sidestore_memory.py",
                    "patch_v34_display_profiles.py", "patch_v36_multitask_chrome.py", "patch_v37_window_overflow.py", "patch_v38_maximized_safe_area.py", "patch_v39_dock_app_switch_only.py", "patch_v41_remove_floating_return.py", "patch_v43_sidejit_dns_guard.py", "patch_v45_builtin_settings.py", "patch_v46_keyboard_window_scope.py", "patch_v46_jit_recovery.py", "patch_v46_jit_host_bundle.py",
                    "patch_v47_resume.py", "patch_v47_jit_transport.py", "patch_v47_portal_budget.py", "patch_v48_madeira_runtime_probe.py", "patch_v49_auto_jit.py", "patch_v50_stikdebug_protocol.py",
                    "patch_v55_rotation_geometry.py", "patch_v55_memory_probe.py", "patch_v56_notch_ui.py",
                    "patch_v57_ota_identity.py", "patch_v58_fullscreen.py",
                    "patch_v58_native_activity.py", "patch_v60_island_guest_switch.py", "patch_v192_startup.py",
                    "patch_v66_four_ids.py", "patch_v67_three_ids.py", "v67_upstream_watch.py", "run_bounded_build.py", "v68_appid_minimizer.py", "patch_v69_signing_udid_retry.py",
                    "xtool_nrg_auth_compat.py", "xtool_nrg_auth_cpd_v3.py",
                    "xtool_nrg_auth_resync_v4.py", "xtool_nrg_auth_trace.py", "xtool_nrg_auth_503_v5.py",
                    "patch_v72_overflow_longpress.py", "patch_v73_apple_floating_control.py",
                    "patch_v75_retained_guest_reconcile.py",
                    "patch_v76_native_guest_switcher.py",
                    "patch_v77_profile_8220_device_registration.py",
                    # V78: private symbol safety guards and alternative macOS CI runner.
                    "patch_v78_nud_symbol_crashguard.py", "run_v78_codemagic.py",
                    "patch_v79_dyld_vtable_crashguard.py", "run_v79_codemagic.py",
                    "run_v80_codemagic.py", "patch_v81_arm64ex1_litehook.py",
                    "patch_v84_asset_catalog.py", "patch_v86_verified_dead_guest_reconcile.py",
                    "patch_v97_retained_guest_host_rebind.py", "patch_v98_gsa_80046_trace.py",
                    "patch_v100_morph_guest_switcher.py", "patch_v100_native_guest_morph.py",
                    "patch_v102_guest_recent_coherence.py",
                    "patch_v102_unified_window_actions.py",
                    "patch_v102_retire_native_gestures.py",
                    "patch_v103_single_guest_control.py",
                    "patch_v104_guest_scene_reactivation.py",
                    "patch_v105_delete_legacy_return.py",
                    "audit_v102_final_source.py", "audit_v107_active_guest_ui.py",
                    "patch_v107_retire_dead_return_settings.py",
                    "patch_v108_remove_blue_collapsed_dock.py",
                    "patch_v109_gsa_auth_guidance.py",
                    "patch_v110_single_guest_dock.py",
                    "patch_v110_gsa_http_phase.py",
                    "patch_v116_sideinstaller_gsa.py",
                    "verify_v88_canonical_guest_sources.py"},
        )

    def test_patch_scripts_parse_and_contain_guard_markers(self):
        """Syntax and guard-marker checks; actual repeat-application tests live beside patch fixtures.

        Examples include test_automation, test_app_layout, test_embedded_keychain,
        test_guest_return, test_sidesign_privacy, and test_v3_unified_shell.
        """
        for name in REQUIRED_SCRIPTS | {LIVE_CONTAINER_SCRIPT, LIVE_CONTAINER_STARTUP_SCRIPT,
                                        COMBINED_REFRESH_SCRIPT, EMBEDDED_KEYCHAIN_SCRIPT, "patch_combined_transport.py", "patch_refresh_result_bridge.py", APP_LAYOUT_SCRIPT, V3_UNIFIED_SHELL_SCRIPT,
                                        "patch_sidesign_2fa_state.py"}:
            path = SCRIPTS / name
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        self.assertIn(
            "if MARKER in text",
            (SCRIPTS / "patch_background_automation.py").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "if MARKER in text",
            (SCRIPTS / "patch_coredevice_idevice.py").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "if MARKER in text",
            (SCRIPTS / "patch_sidestore_integration.py").read_text(encoding="utf-8"),
        )

    def test_workflow_references_current_scripts(self):
        workflow = WORKFLOW.read_text(encoding="utf-8")
        references = set(re.findall(r"builder/scripts/([A-Za-z0-9_.-]+\.py)", workflow))
        self.assertTrue(REQUIRED_SCRIPTS.issubset(references))
        self.assertNotRegex(workflow, r"builder/scripts/patch_v\d+")
        self.assertNotIn("build-v29-coredevice-self-refresh.yml", workflow)
        live_workflow = (ROOT / ".github/workflows/livecontainer-build.yml").read_text(encoding="utf-8")
        self.assertIn("builder/scripts/" + LIVE_CONTAINER_STARTUP_SCRIPT, live_workflow)
        self.assertIn("builder/scripts/" + COMBINED_REFRESH_SCRIPT, live_workflow)
        self.assertIn("builder/scripts/patch_app_layout.py", live_workflow)
        self.assertIn("builder/scripts/" + V3_UNIFIED_SHELL_SCRIPT, live_workflow)
        self.assertIn("builder/scripts/patch_sidesign_2fa_state.py", live_workflow)
        standalone_workflow = (ROOT / ".github/workflows/build-current.yml").read_text(encoding="utf-8")
        self.assertIn("builder/scripts/patch_app_layout.py", standalone_workflow)
        contract = (SCRIPTS / COMBINED_REFRESH_SCRIPT).read_text(encoding="utf-8")
        self.assertIn("from patch_embedded_keychain import patch as patch_shared_keychain", contract)
        self.assertIn("patch_combined_cli(Path(sys.argv[1]))", contract)
        self.assertIn("patch_shared_keychain(staged)", contract)
        self.assertLess(contract.index("patch_shared_keychain(staged)"),
                        contract.index("_patch_verified(staged)", contract.index("patch_shared_keychain(staged)")))
        self.assertIn("[LC_KEYCHAIN] GROUP_SELECTED", contract)
        self.assertIn("verify_keychain_selection_contract", contract)

    def test_upstream_ipsec_anchor_preserves_original_punctuation(self):
        source = (SCRIPTS / "patch_sidestore_integration.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        anchors = [
            ast.literal_eval(node.value)
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "old_ipsec_requirement"
                    for target in node.targets)
        ]
        self.assertEqual(len(anchors), 1)
        self.assertIn("interface found \u2014 LocalDevVPN", anchors[0])
        self.assertNotIn(chr(0x2014), source)

    def test_no_sensitive_paths_are_reachable(self):
        # Retain the audit of every reachable ref, including deleted files in
        # history. A clone containing private investigation refs must fail.
        result = subprocess.run(
            ["git", "-c", "core.quotePath=false", "rev-list", "--objects", "--all"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        reachable_paths = [parts[1] for line in result.stdout.splitlines()
                           if len(parts := line.split(maxsplit=1)) == 2]
        self.assertFalse(
            [path for path in reachable_paths if _is_sensitive_reachable_path(path)],
            "reachable repository contains sensitive artifact paths",
        )

    def test_sensitive_path_classifier_preserves_security_boundary(self):
        self.assertFalse(_is_sensitive_reachable_path("scripts/adapt_sidestore_070_pairing.py"))
        self.assertFalse(_is_sensitive_reachable_path("tests/PairingFile.swift"))
        self.assertTrue(_is_sensitive_reachable_path("PairingFile"))
        self.assertTrue(_is_sensitive_reachable_path("private/client_cert.pem"))
        self.assertTrue(_is_sensitive_reachable_path("scripts/client.p12"))
        self.assertTrue(_is_sensitive_reachable_path("diagnostics/LockdownDirectDiag.log"))
        self.assertTrue(_is_sensitive_reachable_path("docs/export.der"))
        for path in ("scripts/pairingFile.json", "tests/rppairing.plist",
                     "data/device.pairing", "backups/pairingFile.plist.old",
                     "exports/client_key.backup", "LockdownDirectDiag/output.log",
                     "docs/CLIENT.P12", "scripts/key.pem", "data/phone.pfx"):
            with self.subTest(path=path):
                self.assertTrue(_is_sensitive_reachable_path(path))

    def test_public_docs_do_not_expose_known_private_network_details(self):
        """Generic RFC1918 examples are allowed; known diagnostic addresses are not."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        verification = (ROOT / "docs" / "VERIFICATION.md").read_text(encoding="utf-8")
        public_docs = readme + "\n" + verification

        # These were diagnostic/local addresses and must never leak into public docs.
        for sensitive_ip in ("10.7.0.1", "10.7.0.2"):
            self.assertNotIn(sensitive_ip, public_docs)

        # Documentation may intentionally use RFC1918 examples such as
        # 10.0.0.x or 192.168.1.x to explain same-subnet LocalDevVPN routing.
        self.assertIn("same subnet", readme)
        self.assertIn("/32", readme)


if __name__ == "__main__":
    unittest.main()
