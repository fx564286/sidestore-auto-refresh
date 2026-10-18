# V48 — Madeira as a LiveContainer guest

The user's Madeira JIT script showed `vAttach -> T11` followed by optional
`QSetIgnoredExceptions -> E35` and `QPassSignals -> unsupported`. These replies
do not prove allocation or execution of the JIT memory pool.

Madeira is a guest in LiveContainer, so its **effective process signature** is
the actual running LiveContainer or LiveProcess signature, not the entitlements
in the loose Madeira IPA. The V46 host-return path remains untouched.

V48 passively logs `[NRG_V48_GUEST_RUNTIME]` at `guest_bootstrap` and
`foreground_after_debugger`, with PID, LiveProcess role, `CS_DEBUGGED`,
`get-task-allow`, `P_TRACED`, effective `increased-memory-limit` and
`extended-virtual-addressing` grants. A -1 indicates the query failed.
`jit_pool_unverified=1` explicitly says this is NOT executable JIT proof.

No debugger attach, executable memory mapping, Apple registration, credential,
keyboard, audio, or app storage changes are made by this probe. Existing
widgetless 4-profile installer is retained as a V48-branch-locked upgrade path:
`scripts/nrg_v48_widgetless_install_oneclick.sh <successful-run-id>`.

## On-device acceptance

1. Verify the original host Bundle ID and extension set; upgrade, never uninstall.
2. Launch Madeira inside LiveContainer, obtain `[NRG_V48_GUEST_RUNTIME]`.
3. Trigger `Enable JIT` inside Madeira, complete the StikDebug flow and return.
4. Compare `cs_debugged` and `traced` after foreground return, **then** check
   Madeira's real JIT pool allocation and JIT-required game behavior.
5. Check `memory_granted`. A 1 proves entitlement presence in the process,
   not unlimited RAM. A 0 or -1 demands profile/signature diagnosis, not a
   claimed increase in iOS jetsam limits.
6. Separately exercise V47 long-idle keyboard/audio resume regressions.

Device results remain unverified until the V48 build is installed and tested.
