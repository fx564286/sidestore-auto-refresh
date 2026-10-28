# Scarlet Crystal GitHub Actions: accurate + fast

## Safety / existing V149 run

This configuration is isolated in the **ci/scarlet-quality-speed-20261028**
branch. It does not commit to or update **build/scarlet-fast-ci** or
**fix/scarlet-v149-controls-only-20261028**. Those refs retain their
original workflow and concurrent runs.

The long workflow uses `concurrency.group: livecontainer-${{ github.ref }}`.
The new lightweight preflight workflow uses the **distinct**
`scarlet-preflight-${{ github.ref }}` group and
`cancel-in-progress: false`. Changes here cannot cancel V149's original run.

## GitHub UI

In Actions > **LiveContainer embedded SideStore build** > **Run workflow**:
select this optimization branch and the `profile` input.

- **fast**: Fail-closed static preflight plus focused UI tests, original source
  patch assertions, Xcode host+SideStore compilation, Rust transport
  validation, IPA provenance, Mach-O archive verification. The historical
  all-tests-before-patches sweep is **not run**. This is a *test IPA*, not
  release validation; artifact name says `fast`.
- **release** (default): everything in fast **plus** the original complete
  `run_required_tests.py` suite, skip-allowlist gate and full release
  verification. All *push-triggered* builds use release, never fast.
  The artifact name says `release`.

The independent **Scarlet Crystal fast CI preflight** workflow checks code
and metadata only, on an Ubuntu runner; **it does not compile iOS or publish**.

## Quality controls

1. Validate version and label consistency between app plist stamping,
   build package metadata, filename, and CI assertions before any Xcode work.
2. Intentionally corrupt the label/version in tests and require that
   the preflight fail. This catches the past V149 -> V148 stale-grep defect.
3. Retain Swift syntax parsing, targeted generated-source tests,
   full Xcode build, Rust transport, IPA integrity and archive/Mach-O checks.
4. Preserve all source pin hashes, Apple developer profiles, certificates and
   bundle IDs. This change modifies **no app source**.
5. Keep Cargo build cache keyed by toolchain, pinned revisions and source
   digests; keep independent archive action with Xcode DerivedData reuse.
6. Upload an explicit CI profile attestation so fast test artifacts cannot be
   mistaken for a full-suite validated release.

Speed improvement is measured by comparing completed GitHub Actions runs;
do not claim a numerical speedup before two runs are completed.

## Rollout

A push of this branch triggers **only** the lightweight new preflight
workflow, not the long build. A manual fast/release run may be started after
the original V149 run finishes. This avoids competing Xcode runner load and
guarantees the existing V149 run is not canceled or restarted.
