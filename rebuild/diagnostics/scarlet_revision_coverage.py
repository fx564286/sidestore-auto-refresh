"""Fail closed if a source commit has no versioned, file-specific remediation receipt.

R6P15's proposal guard validates *entries*, not whether every later source edit
created an entry. This second gate audits the actual Git commits since R6P15.
The P15 archive is SHA-256 frozen; after P15, append new entries rather than
silently rewriting prior failures or replacing them with a summary.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ANCHOR = "a3eedc4174c9db698065ecfee7c7da6a9ac316b8"
FROZEN_ENTRIES = 51
FROZEN_SHA256 = "d8edebeff255e193eb6a3eb4d783630c5d4bf89872129b8e9ffc5cae2ddf6e04"
AUDIT_HISTORY = "rebuild/diagnostics/scarlet_remediation_history.json"
WATCH_PREFIXES = (
    "rebuild/HostApp/", "rebuild/Sources/", "rebuild/integration/",
    "rebuild/Tests/", "rebuild/diagnostics/", "rebuild/scripts/",
)
WATCH_EXACT = {".github/workflows/scarlet-paired-engines-build.yml"}


def watched(path: str) -> bool:
    return (path != AUDIT_HISTORY and
            (path in WATCH_EXACT or path.startswith(WATCH_PREFIXES)))


def frozen_fingerprint(entries: list[dict]) -> str:
    raw = json.dumps(entries[:FROZEN_ENTRIES], ensure_ascii=False,
                     sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def inspect_frozen_history(history: dict) -> list[str]:
    entries = history.get("entries", [])
    if len(entries) < FROZEN_ENTRIES:
        return [f"P15 immutable history truncated: {len(entries)} < {FROZEN_ENTRIES}"]
    if frozen_fingerprint(entries) != FROZEN_SHA256:
        return ["P15 immutable L001-L051 history altered; append a new record instead"]
    return []


def uncovered_changes(changes: list[tuple[str, str]], entries: list[dict]) -> list[str]:
    """Require a receipt with the *same commit AND exact changed file*."""
    receipts = set()
    for entry in entries[FROZEN_ENTRIES:]:
        revisions = {r.get("sha") for r in entry.get("source_revisions", [])
                     if isinstance(r, dict)}
        paths = {loc.get("file") for loc in entry.get("code_locations", [])}
        for sha in revisions:
            for path in paths:
                receipts.add((sha, path))
    return [f"UNRECORDED SOURCE COMMIT {sha[:12]} {path}"
            for sha, path in changes if watched(path) and (sha, path) not in receipts]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def verify_repo(history: dict, repo: Path, base: str = ANCHOR) -> list[str]:
    errors = inspect_frozen_history(history)
    if errors:
        return errors
    try:
        # Fail closed if CI was shallow-cloned or is not descending from P15.
        _git(repo, "merge-base", "--is-ancestor", base, "HEAD")
        commits = _git(repo, "rev-list", "--reverse", f"{base}..HEAD").splitlines()
        changes = []
        for sha in commits:
            files = _git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", sha)
            changes.extend((sha, path) for path in files.splitlines() if watched(path))
    except (subprocess.CalledProcessError, OSError) as exc:
        return ["Cannot audit full P15..HEAD Git revisions: " + str(exc)]
    errors.extend(uncovered_changes(changes, history.get("entries", [])))
    # An archived revision must correspond to a real post-anchor source change;
    # reject a fake receipt pasted into JSON to silence an uncovered commit.
    actual = set(changes)
    for entry in history.get("entries", [])[FROZEN_ENTRIES:]:
        revs = {r.get("sha") for r in entry.get("source_revisions", [])
                if isinstance(r, dict)}
        paths = {p.get("file") for p in entry.get("code_locations", [])
                 if watched(str(p.get("file", "")))}
        for path in paths:
            if not any((sha, path) in actual for sha in revs):
                errors.append(f"{entry.get('id')}: source diff not found at recorded commit: {path}")
    return errors
