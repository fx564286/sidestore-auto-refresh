"""R6P121: prove CI uses mutually exclusive branch selectors for IPA and Release."""
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / '.github/workflows/scarlet-paired-engines-build.yml').read_text()
REF_122 = 'refs/heads/fix/scarlet-v48-r6p122-device-guest-catalog-20261120'
REF_121 = 'refs/heads/fix/scarlet-v48-r6p121-existing-cert-recovery-20261120'
REF_120 = 'refs/heads/fix/scarlet-v48-r6p120-manual-owner-mismatch-20261120'
EXPECTED_ASSET_122 = 'Scarlet-Crystal-V48-R6P122-DEVICE-GUEST-CATALOG-UNSIGNED.ipa'
EXPECTED_ASSET_121 = 'Scarlet-Crystal-V48-R6P121-EXISTING-CERT-RECOVERY-UNSIGNED.ipa'
EXPECTED_ASSET_120 = 'Scarlet-Crystal-V48-R6P120-MANUAL-OWNER-MISMATCH-UNSIGNED.ipa'
EXPECTED_TAG_122 = 'scarlet-v48-r6p122-device-guest-catalog-unsigned-20261120'
EXPECTED_TAG_121 = 'scarlet-v48-r6p121-existing-cert-recovery-unsigned-20261120'
EXPECTED_TAG_120 = 'scarlet-v48-r6p120-manual-owner-mismatch-unsigned-20261120'


def shell_selectors():
    lines = WORKFLOW.splitlines()
    needle = f'if [ "$GITHUB_REF" = "{REF_122}" ]; then'
    starts = [i for i, line in enumerate(lines) if line.strip() == needle]
    if len(starts) != 3:
        raise AssertionError(f'Expected three distinct R6P122 selector blocks, got {len(starts)}')
    selectors = []
    for start in starts:
        indent = len(lines[start]) - len(lines[start].lstrip())
        # The original source has one independent `fi` before R6P120,
        # which is exactly the regression this test catches.
        closing = next(i for i in range(start + 1, len(lines))
                       if lines[i].strip() == 'fi' and
                       len(lines[i]) - len(lines[i].lstrip()) == indent)
        selectors.append('\n'.join(lines[start:closing + 1]))
    return selectors


def resolve(selector, ref):
    code = ('set -Eeuo pipefail\n'
            'SCARLET_HOST_VERSION_ARGS=(__unset__)\n'
            'asset=none\n'
            'tag=none\n'
            + selector + '\n'
            'printf "version=%s\\nasset=%s\\ntag=%s\\n" '
            '"${SCARLET_HOST_VERSION_ARGS[*]}" "$asset" "$tag"\n')
    result = subprocess.run(['bash', '-c', code], capture_output=True,
                            text=True, check=True, timeout=10,
                            env={**os.environ, 'GITHUB_REF': ref})
    return dict(line.split('=', 1) for line in result.stdout.splitlines())


class R6P121ReleaseChain(unittest.TestCase):
    def test_r6p121_must_precede_r6p120_in_same_if_elif_chain(self):
        for selector in shell_selectors():
            with self.subTest(selector=selector[:100]):
                r121 = f'elif [ "$GITHUB_REF" = "{REF_121}" ]; then'
                r120 = f'elif [ "$GITHUB_REF" = "{REF_120}" ]; then'
                self.assertIn(r121, selector)
                self.assertIn(r120, selector)
                self.assertLess(selector.index(r121), selector.index(r120))
                self.assertNotIn(f'if [ "$GITHUB_REF" = "{REF_120}" ]; then',
                                 '\n'.join(line for line in selector.splitlines()
                                           if line.strip().startswith('if ')))

    def test_r6p122_native_version_asset_and_release_are_exact(self):
        version, packaging, publishing = shell_selectors()
        self.assertEqual(resolve(version, REF_122)['version'], '--host-build-version 3.8.122')
        self.assertEqual(resolve(packaging, REF_122)['asset'], EXPECTED_ASSET_122)
        output = resolve(publishing, REF_122)
        self.assertEqual(output['tag'], EXPECTED_TAG_122)
        self.assertEqual(output['asset'], EXPECTED_ASSET_122)

    def test_r6p121_native_version_and_asset_and_release_are_exact(self):
        version, packaging, publishing = shell_selectors()
        self.assertEqual(resolve(version, REF_121)['version'], '--host-build-version 3.8.121')
        self.assertEqual(resolve(packaging, REF_121)['asset'], EXPECTED_ASSET_121)
        output = resolve(publishing, REF_121)
        self.assertEqual(output['tag'], EXPECTED_TAG_121)
        self.assertEqual(output['asset'], EXPECTED_ASSET_121)

    def test_r6p120_identity_is_unchanged(self):
        version, packaging, publishing = shell_selectors()
        self.assertEqual(resolve(version, REF_120)['version'], '--host-build-version 3.8.120')
        self.assertEqual(resolve(packaging, REF_120)['asset'], EXPECTED_ASSET_120)
        output = resolve(publishing, REF_120)
        self.assertEqual(output['tag'], EXPECTED_TAG_120)
        self.assertEqual(output['asset'], EXPECTED_ASSET_120)


if __name__ == '__main__':
    unittest.main()
