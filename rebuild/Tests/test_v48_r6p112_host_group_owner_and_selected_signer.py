"""P112 source contracts. These do not prove real iPhone reinstallation.

Do not conflate (1) signed host IPC group and (2) Apple ID/Team
selected to provision a new IPA. Real iPhone installation/profile
replacement requires a separate signed-device receipt.
"""
from pathlib import Path
import unittest

R=Path(__file__).resolve().parents[2]
HOST=(R/'rebuild/HostApp/ScarletIntegratedHostView.swift').read_text()
READINESS=(R/'rebuild/HostApp/ScarletSigningReadinessPanel.swift').read_text()
WORKER=(R/'rebuild/integration/ScarletDeviceInstallAgent.swift.txt').read_text()
WIRE=(R/'rebuild/integration/wire_scarlet_auth.py').read_text()
CERT=(R/'rebuild/integration/ScarletGuestCertificateAgent.swift.txt').read_text()
SIGNIN=(R/'rebuild/integration/ScarletGuestSignInAgent.swift.txt').read_text()
AUTO=(R/'rebuild/HostApp/ScarletAutomaticRenewal.swift').read_text()
PAIR=(R/'rebuild/HostApp/ScarletNativeDevicePairing.swift').read_text()
FLOW=(R/'.github/workflows/scarlet-paired-engines-build.yml').read_text()

def signed_host_group(team, groups):
    valid=len(team.encode('ascii','ignore'))==10 and all(
        x in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' for x in team)
    group='group.com.SideStore.SideStore.'+team
    return group if valid and group in groups else None

class NativeSignedHostIdentity(unittest.TestCase):
    def test_host_and_guest_stage_authorized_by_actual_signed_host_not_selected_ipa_team(self):
        for src in (READINESS,WORKER,WIRE):
            self.assertIn('SecTaskCopyValueForEntitlement(',src)
            self.assertIn('"com.apple.developer.team-identifier" as CFString',src)
            self.assertIn('"com.apple.security.application-groups" as CFString',src)
        self.assertIn('ScarletSigningReadiness.authorizedSideStoreGroupID()',HOST)
        self.assertIn('let groupID = "group.com.SideStore.SideStore." + team',READINESS)
        self.assertIn('let signedGroupID = "group.com.SideStore.SideStore." + team',WORKER)
        self.assertIn('let groupID = "group.com.SideStore.SideStore." + signedTeam',WIRE)
        self.assertIn('groups.contains(groupID)',READINESS)
        self.assertIn('groups.contains(signedGroupID)',WORKER)
        self.assertIn('groups.contains(groupID)',WIRE)
        self.assertNotIn('group.com.SideStore.SideStore.P8EZT3U5N4',HOST+WORKER+WIRE)
        self.assertIn('owner.teamID == expectedTeamID',WORKER)
        self.assertIn('activeAccounts[0].teamID == pinnedTeamID',HOST)
        self.assertIn('identifier: "scarlet.install.ipa." + teamID',WIRE)

    def test_one_signed_team_can_stage_two_different_ipa_owners_without_moving_group(self):
        # Static policy model of the same precise data flow. P112 does
        # not mutate the entitlements, active login or certificate store.
        A='P8EZT3U5N4'
        B='J82MWRXY89'
        self.assertEqual(signed_host_group(A,{'group.com.SideStore.SideStore.'+A}),
                         'group.com.SideStore.SideStore.'+A)
        self.assertEqual(signed_host_group(B,{'group.com.SideStore.SideStore.'+B}),
                         'group.com.SideStore.SideStore.'+B)
        self.assertIsNone(signed_host_group(B,{'group.com.SideStore.SideStore.'+A}))
        self.assertIsNone(signed_host_group('invalid!',{'group.com.SideStore.SideStore.invalid!'}))
        self.assertNotIn('deleteItem(',HOST+WORKER)

    def test_legacy_certificate_never_exposes_ambient_global_key_without_owner_pin(self):
        self.assertNotIn('"P8EZT3U5N4"',CERT)
        self.assertIn('ScarletInstallTeamAuthority.activeOwnership()',CERT)
        self.assertIn('ScarletInstallTeamAuthority.issue(',CERT)
        self.assertIn('teamID: selected.teamID, forceNew: false',CERT)
        self.assertIn('ScarletInstallTeamAuthority.activeSelectedSignerSerial(',CERT)
        self.assertIn('active.serialNumber.lowercased() == pinnedSerial',CERT)
        self.assertIn('active.serialNumber.lowercased() == pinned',CERT)
        self.assertIn('ownerNow.appleID == selected.appleID',CERT)
        self.assertNotIn('revokeCertificate(',CERT)
        self.assertNotIn('SecItemDelete(',CERT)
        self.assertNotIn('CertificateProvisioningFlow(handler: nil)',CERT)

    def test_default_host_team_identity_is_actual_entitlement_when_required(self):
        self.assertNotIn('let expectedTeamID = "P8EZT3U5N4"',SIGNIN)
        self.assertIn('let signedHostTeamID = SecTaskCopyValueForEntitlement(',SIGNIN)
        self.assertIn('if requireHostTeam && team.identifier != expectedTeamID',SIGNIN)
        self.assertIn('.ensureActiveTeamForRefresh(requireHostTeam: false)',(
            R/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text())
        for text in (AUTO,PAIR):
            self.assertIn('let signedHost = ScarletSigningReadiness.inspect()',text)
            self.assertIn('signedHost.signedApplicationIdentifierMatches',text)
            self.assertNotIn('actual == original + ".P8EZT3U5N4"',text)

    def test_new_issue_portal_error_remains_distinct_from_host_group_fix(self):
        # P111 device trace observed 20/other at Apple create; neither
        # fakes success nor changes existing selected-Team fresh issuer.
        native=(R/'rebuild/integration/ScarletGuestSavedAccounts.swift.txt').read_text()
        self.assertIn('DeveloperPortalProxy.shared.createCertificate(',native)
        self.assertIn('forceNew: true',native)
        self.assertIn('selected_team_certificate_portal_failed',native)
        self.assertNotIn('revokeCertificate(',CERT+WORKER)

    def test_p112_native_release_is_unique_and_public_unsigned_only(self):
        for x in ('fix/scarlet-v48-r6p112-remove-runtime-team-literals-20261118',
                  '--host-build-version 3.8.112',
                  'version="3.8.112"',
                  'Scarlet-Crystal-V48-R6P112-RUNTIME-OWNER-UNSIGNED.ipa',
                  'scarlet-v48-r6p112-runtime-owner-unsigned-20261118',
                  'scarlet.certificate.selected_signer_unverified'):
            self.assertIn(x,FLOW)

if __name__=='__main__':unittest.main()
