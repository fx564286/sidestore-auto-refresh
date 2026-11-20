"""Unique signed-host binary identity and public unsigned release for R6P126."""
from pathlib import Path
import unittest

WF = (Path(__file__).resolve().parents[2] / ".github/workflows/scarlet-paired-engines-build.yml").read_text()
BRANCH = "fix/scarlet-r6p124-apps-grid-balance-20261121"
ASSET = "Scarlet-Crystal-V48-R6P126-UNIFIED-LAUNCHER-UNSIGNED.ipa"
TAG = "scarlet-v48-r6p126-unified-launcher-unsigned-20261121"

class ReleaseIdentityTests(unittest.TestCase):
    def test_r6p126_own_build_version_not_shared_with_audio_r6p124(self):
        self.assertIn('refs/heads/' + BRANCH, WF)
        self.assertIn('SCARLET_HOST_VERSION_ARGS=(--host-build-version 3.8.126)', WF)
        self.assertIn('if __import__("os").environ.get("GITHUB_REF", "") == "refs/heads/' + BRANCH + '": version="3.8.126"', WF)
        self.assertIn('assert info["CFBundleVersion"]==version', WF)

    def test_release_only_publishes_unique_signed_host_binary_identity(self):
        release = WF.split("  publish-unsigned-github-release:", 1)[1]
        self.assertIn("github.ref == 'refs/heads/" + BRANCH + "'",release.split("    runs-on:", 1)[0])
        self.assertIn('tag=' + TAG,release)
        self.assertEqual(release.count(ASSET),2)
        # The published asset is new, not the previous audio-focus IPA.
        self.assertNotEqual(ASSET, "Scarlet-Crystal-V48-R6P124-GUEST-AUDIO-FOCUS-UNSIGNED.ipa")

    def test_actual_shell_selectors_produce_consistent_identity(self):
        from test_v48_r6p121_release_identity_chain import shell_selectors, resolve
        version, packaging, publishing = shell_selectors()
        ref = "refs/heads/" + BRANCH
        self.assertEqual(resolve(version, ref)["version"], "--host-build-version 3.8.126")
        self.assertEqual(resolve(packaging, ref)["asset"], ASSET)
        self.assertEqual(resolve(publishing, ref)["asset"], ASSET)
        self.assertEqual(resolve(publishing, ref)["tag"], TAG)

    def test_release_changes_do_not_touch_native_identities(self):
        self.assertIn('assert info["CFBundleIdentifier"]=="com.kdt.livecontainer.P8EZT3U5N4"', WF)
        self.assertIn('assert info["CFBundleShortVersionString"]=="3.8.11"', WF)

if __name__ == "__main__":
    unittest.main()
