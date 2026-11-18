"""P115 signed-host CoreData owner reconciliation: fail closed unless exact provenance."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKER = (ROOT / "rebuild/integration/ScarletGuestRefreshAgent.swift.txt").read_text()
WORKFLOW = (ROOT / ".github/workflows/scarlet-paired-engines-build.yml").read_text()


class ManagedHostOwnerReconciliation(unittest.TestCase):
    def test_only_host_owned_signed_profile_and_pinned_signer(self):
        function = WORKER.split("private func performRegistration(", 1)[1].split(
            "\n}\n\n// P102:", 1)[0]
        for phrase in (
            "profile.teamIdentifier == owner.teamID",
            "verifiedInstalledHostID(hostBundlePath: hostBundlePath) == bundleID",
            "for: currentTeamID, appleID: owner.appleID",
            "ownerSigner.x509.expiryDate > Date()",
            "CacheAppOperation.cachePayload(for: hostURL)",
            "cachedHost.provisioningProfile?.teamIdentifier == currentTeamID",
            ".getSigningCertificate(at: hostURL)?.serialNumber",
            "caseInsensitiveCompare(ownerSigner.serialNumber)",
            "hostRows.count <= 1",
            "existing.isActive",
            "existing.bundleIdentifier == bundleID",
            "teams.count == 1",
            "oldExtensionIDs == signedExtensionIDs",
            "existing.team = selectedTeam",
            "existing.update(resignedAppBundle: signedHost,",
            "existing.appBundleFingerprint = signature",
            "try context.save()",
            'return "host_managed_owner_reconciled"',
        ):
            self.assertIn(phrase, function)
        self.assertLess(function.index("signedOwnerProven"), function.index("existing.team = selectedTeam"))
        self.assertLess(function.index("hostRows.count <= 1"), function.index("existing.team = selectedTeam"))
        self.assertLess(function.index("oldExtensionIDs == signedExtensionIDs"),
                        function.index("existing.team = selectedTeam"))

    def test_existing_owner_and_inactive_records_unchanged(self):
        function = WORKER.split("private func performRegistration(", 1)[1].split(
            "\n}\n\n// P102:", 1)[0]
        self.assertIn('return existing.isActive ? "already_managed" :', function)
        self.assertIn('"host_managed_record_inactive"', function)
        self.assertIn('return "host_managed_owner_mismatch"', function)
        self.assertIn('return "host_managed_duplicate_records"', function)
        self.assertIn('return "host_managed_extensions_mismatch"', function)
        for forbidden in ("SecItemDelete(", "revokeCertificate(", "removeItem(at: hostURL)",
                          "AppManager.shared.install(", "existing.isActive = true"):
            self.assertNotIn(forbidden, function)

    def test_success_readback_receipt_and_bootstrap_cache(self):
        self.assertIn('result == "host_managed_owner_reconciled"', WORKER)
        self.assertIn('"host_managed_duplicate_records", "host_managed_extensions_mismatch"', WORKER)

    def test_native_ci_and_unique_install_identity(self):
        branch = "fix/scarlet-v48-r6p115-managed-host-owner-20261119"
        self.assertIn(branch, WORKFLOW)
        self.assertIn("--host-build-version 3.8.115", WORKFLOW)
        self.assertIn('version="3.8.115"', WORKFLOW)
        self.assertIn("R6P115-MANAGED-OWNER-UNSIGNED.ipa", WORKFLOW)
        self.assertIn("scarlet-v48-r6p115-managed-owner-unsigned-20261119", WORKFLOW)


if __name__ == "__main__":
    unittest.main()
