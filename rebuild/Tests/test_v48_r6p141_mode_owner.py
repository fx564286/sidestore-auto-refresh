from pathlib import Path
import unittest
import importlib.util, json, plistlib, tempfile, zipfile
R=Path(__file__).resolve().parents[1]
S=(R/'HostApp/ScarletFullscreenSceneStack.swift').read_text()
H=(R/'HostApp/ScarletIntegratedHostView.swift').read_text()
class ResidentModeOwner(unittest.TestCase):
    def test_provisional_owner_survives_hidden_viewport(self):
        body=S.split('var hasResidentSession: Bool {',1)[1].split('var hasLiveResidentProcess',1)[0]
        self.assertIn('if slot.pid <= 0 { return true }',body)
        self.assertNotIn('return isVisible',body)
        self.assertIn('if experimentalFullscreenResident || fullscreenStack.hasResidentSession',H)
    def test_common_admission_rechecks_persisted_mode_before_mutation(self):
        body=S.split('func enqueueSignedGuest(_ app: LCAppModel) throws {',1)[1].split('func attach(',1)[0]
        self.assertIn('guard residentModeEnabled else',body)
        self.assertLess(body.index('guard residentModeEnabled else'),body.index('slots.append('))
        self.assertIn('UserDefaults.standard.bool(forKey: "Scarlet.Feature.FullscreenResidentPilot.V45")',S)
    def test_automatic_fallback_cannot_override_disabled_mode(self):
        body=S.split('private func recoverFastFailedGuest(',1)[1].split('private func revealStartedScene(',1)[0]
        self.assertIn('guard residentModeEnabled,',body)
        self.assertIn('guard self.residentModeEnabled else',body)
        self.assertLess(body.index('guard self.residentModeEnabled else'),body.index('defaults.set(folder'))

    def test_cumulative_archive_rejects_missing_mode_admission(self):
        spec = importlib.util.spec_from_file_location(
            "gate139", R / "integration/verify_integrated_release.py")
        gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gate)
        sha = "d" * 40
        host = "Frameworks/LiveContainerSwiftUI.framework/LiveContainerSwiftUI"
        worker = "Frameworks/SideStoreApp.framework/SideStore"
        actions = {k: {} for k in ("RefreshAllIntent", "RefreshAllAppsWidgetIntent", "InstallIPAIntent")}
        actions["ScarletSelfUpdateIntent"] = {"fullyQualifiedTypeName": "LiveContainerSwiftUI.ScarletSelfUpdateIntent"}
        with tempfile.TemporaryDirectory() as tmp:
            ipa = Path(tmp) / "candidate.ipa"
            for include in (False, True):
                with zipfile.ZipFile(ipa, "w") as z:
                    z.writestr(gate.PREFIX + "Info.plist", plistlib.dumps({
                        "CFBundleIdentifier": "com.kdt.livecontainer.P8EZT3U5N4",
                        "CFBundleShortVersionString": "3.8.11",
                        "CFBundleVersion": "3.8.141", "CFBundleExecutable": "LiveContainer"}))
                    for path, markers in gate.REQUIRED_MARKERS.items():
                        data = list(markers)
                        if path == host:
                            data.extend([("scarlet-source-commit:" + sha).encode(),
                                         b"ScarletSelfUpdateIntent", b"shortcut_update_installed_build_verified",
                                         b"classic_handoff_drained", b"classic_handoff_blocked",
                                         b"selected_team_partial_refresh_results", b"selected_team_refresh_result_mismatch",
                                         b"profile_readback_request_busy", b"Scarlet.Refresh.InstalledProfileReceipt.V138", b"automatic_deferred_account_generation_changed", b"profile_readback_retained_uncertain_native_failure"])
                            if include:
                                data.append(b"resident_launch_mode_revoked")
                        if path == worker:
                            data.extend([b"self_update_identity_unverified", b"Scarlet self-update signed identity or version mismatch",
                                         b"self_update_archive_unverified", b"Scarlet self-update archive digest mismatch",
                                         b"Scarlet self-update source topology mismatch", b"Scarlet self-update provisioning Team mismatch",
                                         b"SideSign.DeveloperPortalError", b"selected_team_partial_refresh_results",
                                         b"selected_team_refresh_result_mismatch"])
                        z.writestr(gate.PREFIX + path, b"\0".join(data))
                    for path in ("Metadata.appintents/extract.actionsdata",
                                 "Frameworks/LiveContainerSwiftUI.framework/Metadata.appintents/extract.actionsdata"):
                        z.writestr(gate.PREFIX + path, json.dumps({"actions": actions}))
                if include:
                    self.assertFalse(gate.verify(ipa, "3.8.141", sha)["deviceVerified"])
                else:
                    with self.assertRaisesRegex(ValueError, "R141"):
                        gate.verify(ipa, "3.8.141", sha)
