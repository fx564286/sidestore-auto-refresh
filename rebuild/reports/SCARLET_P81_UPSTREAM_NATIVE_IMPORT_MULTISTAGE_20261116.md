# Scarlet Crystal R6P81 — original LiveContainer archive completion / regression gates

Baseline: P80 source `3a26e598b48026b7f80d9e45e70284fe163aff25`.
Pinned reference: original LiveContainer `9108ae624ea001f7d7696d48407f890b48fa2653`, original `unarchive.m` SHA-256 `d488d14ca9a23e9f30d20c171bf70588ed9da1ec56c7b0c735f46e0e2c4367eb`.

## Measured defect and narrow code change
P79 iPhone 3.8.79 `file_import_requested` → `Swift.String/code1` immediately. This does **not** prove which specific native extractor failure occurred. Source inspection **does** prove that the original LiveContainer `unarchive.m::extract` has a write/read second-pass early break but returns `0` unconditionally. P80 tested for a missing top-level `.app` after success. P81 repairs the extract return to require `ARCHIVE_EOF` and disk-writer close not worse than `ARCHIVE_WARN` using the same original implementation, and prevents false success when `.app` is present but `Info.plist` missing. When extraction actually fails, it removes **only the temporary Payload** before trying existing P79 bounded, validated mapped-ZIP fallback. Existing installed guest, signing certificates, Team IDs, source IPA and guest data are not deleted by this patch. There is no change to status bar, safe area, scaling, multitasking, Apple-ID controls, guest audio, keyboard, or pairing.

## Validation gates
1. **Pinned reference SHA / byte-exact patch scope:** compare generated `unarchive.m` with original `git show HEAD:...` from pinned commit. Before fallback, the sole permitted upstream difference is replacement of the final unconditional return with return based on archive completion. Reject any unrelated change.
2. **Local regression contract:** test correct failure/success status and a negative mutation test that **must fail** if the original source is modified elsewhere; preserve original import/sign/replace APIs and verify `Info.plist` requirement.
3. **Native integration:** run after `wire_scarlet_auth.py` + `apply_scarlet_host.py` on pinned engine, before Xcode archive; verify the original native LC importer, the scratch-only fallback and ZIP guard are present. Report `report/p81-upstream-compat.json`.
4. **Full repo regression suite:** includes account/team isolation, signer, SideStore refresh, status-bar, visual semantics and switcher source-level contracts. Compiler output and unsigned IPA metadata are separately checked in `scarlet-paired-engines-build.yml`.
5. **Signed iPhone acceptance, pending:** reuse the exact IPA previously failing, test a valid IPA, malformed/partial IPA, same-Bundle-ID overwrite with preserved guest data, independent account A/B team, app switching with audio/keyboard, native status icons, Island overlap under scroll/rotate/home-reentry, installed iOS bundle version 3.8.81. A CI success is not device success. Real IPA import must reach `import_pipeline_completed` **and** execute in LiveProcess; absence of that evidence remains unresolved.

## Reference reuse / license
Original LiveContainer AGPL-3.0 source is consumed at the pinned SHA by the workflow, not reimplemented from memory. The existing upstream license/attribution must remain intact even if the app is used personally. Reference implementation copying is allowed subject to its actual license and proper integration testing.

## Rollback
Revert P81 source commit to P80 `3a26e598b48026b7f80d9e45e70284fe163aff25` without deleting installed profiles, source IPAs, user data, or signing keys. Keep the entire remediation history for future no-repeat checks. Do not claim Island solved by this archive-only fix.
