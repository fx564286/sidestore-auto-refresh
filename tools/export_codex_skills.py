#!/usr/bin/env python3
"""Read-only Codex skills inventory/export for ChatGPT migration.

No network requests, no plugin registration, and no modification of source files.
The resulting ZIP is meant for review before building a ChatGPT plugin.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import json
import re
import sys
import zipfile
from datetime import datetime, timezone

HOME = Path.home()
SRC_ROOTS = [
    ("primary", HOME / ".codex" / "skills"),
    ("account1", HOME / ".codex-account1" / "skills"),
    ("account2", HOME / ".codex-account2" / "skills"),
]
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache"}
RISKY_NAMES = re.compile(r"(?i)^(?:\.env(?:\..*)?|id_(?:rsa|ed25519|ecdsa).*|.*\.(?:p12|pfx|pem|key|kdbx|mobileprovision)|(?:credentials|secrets|token|auth|cookies)(?:\..*)?)$")
MAX_FILE = 20 * 1024 * 1024
MAX_TOTAL = 120 * 1024 * 1024
MAX_FILES = 1500


def main() -> int:
    parser = argparse.ArgumentParser(description="Export installed Codex skills without changing originals")
    parser.add_argument("--output", type=Path, default=HOME / "Downloads" / "CODEX-SKILLS-EXPORT.zip")
    parser.add_argument("--custom-only", action="store_true", help="Exclude Codex .system skills")
    args = parser.parse_args()

    selected: list[tuple[str, Path, str]] = []
    collisions: set[str] = set()
    for root_tag, root in SRC_ROOTS:
        if not root.is_dir():
            continue
        for manifest in sorted(root.rglob("SKILL.md")):
            if manifest.is_symlink() or not manifest.is_file():
                continue
            folder = manifest.parent
            rel = folder.relative_to(root)
            if args.custom_only and ".system" in rel.parts:
                continue
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            stem = "-".join(rel.parts)
            name = re.sub(r"[^a-zA-Z0-9._-]+", "-", stem).strip("-") or "unnamed"
            key = name
            if key in collisions:
                name = root_tag + "-" + name
            if name in collisions:
                raise RuntimeError(f"Skill name collision: {folder}")
            collisions.add(name)
            selected.append((name, folder, root_tag))

    if not selected:
        print("[ERROR] No SKILL.md files found in standard Codex skill folders.")
        return 2

    files_to_zip: list[tuple[str, Path]] = []
    notes: list[str] = []
    entries: list[dict[str, str | int]] = []
    total_bytes = 0
    for name, folder, tag in selected:
        base_count = 0
        for p in sorted(folder.rglob("*")):
            rel = p.relative_to(folder)
            if any(part in SKIP_DIRS for part in rel.parts):
                continue
            if p.is_symlink():
                notes.append(f"SKIPPED symlink: {p}")
                continue
            if not p.is_file():
                continue
            if any(RISKY_NAMES.match(part) for part in rel.parts):
                notes.append(f"SKIPPED sensitive-looking filename: {p}")
                continue
            sz = p.stat().st_size
            if sz > MAX_FILE:
                notes.append(f"SKIPPED oversized file ({sz} bytes): {p}")
                continue
            total_bytes += sz
            base_count += 1
            files_to_zip.append(("skills/" + name + "/" + rel.as_posix(), p))
        entries.append({"name": name, "origin": str(folder), "source_root": tag, "file_count": base_count})

    if total_bytes > MAX_TOTAL or len(files_to_zip) > MAX_FILES:
        print(f"[ERROR] Export too large: {total_bytes} bytes; {len(files_to_zip)} files. Use --custom-only.")
        return 3

    result = args.output.expanduser().resolve()
    result.parent.mkdir(parents=True, exist_ok=True)
    if result.exists():
        result = result.with_name(result.stem + "-" + datetime.now().strftime("%Y%m%d-%H%M%S") + result.suffix)
    manifest = {
        "format": "codex-skill-review-export-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Review Codex Skill sources before migration to ChatGPT plugin",
        "skills": entries,
        "warnings": notes,
    }
    with zipfile.ZipFile(result, "x", zipfile.ZIP_DEFLATED, compresslevel=8) as z:
        z.writestr("INVENTORY.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        z.writestr("README.txt", "Read-only Codex Skill source export. Does not install any plugin. Review all files for credentials and machine-specific paths before sharing or publishing. Symlinks, secret-like filenames, and files over 20 MiB are excluded.\n")
        for dest, source in files_to_zip:
            z.write(source, dest)
    print(f"[PASS] Skill count: {len(entries)}")
    for e in entries:
        print(f"  - {e['name']}: {e['file_count']} files ({e['source_root']})")
    if notes:
        print(f"[WARN] {len(notes)} exclusions, see INVENTORY.json")
    print(f"[ZIP] {result}")
    print("[NOTE] Nothing uploaded or registered. Review ZIP contents for secrets before sharing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
