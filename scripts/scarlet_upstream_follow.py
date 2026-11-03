#!/usr/bin/env python3
"""Fail-closed, two-upstream Scarlet Crystal source tracker.

LiveContainer/main and LiveContainer/SideStore/LiveContainerSupport are the
actual composition inputs. SideStore/SideStore/develop is an advisory third
stream; it must NOT silently replace the LiveContainer-maintained fork.

Pinned nested submodules are taken from the matching SideStore fork git tree
rather than combining unrelated SHA versions. Never alters app identity,
provisioning, saved pairing records, or Scarlet patches.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.request

UPSTREAMS = {
    "LIVE_CONTAINER_REF": ("LiveContainer/LiveContainer", "main"),
    "EMBEDDED_SIDESTORE_REF": ("LiveContainer/SideStore", "LiveContainerSupport"),
}
SUBMODULES = {
    "MINIMUXER_REF": "Dependencies/minimuxer",
    "SIDESIGN_REF": "Dependencies/SideSign",
}
ADVISORY = ("SideStore/SideStore", "develop")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def api_get(url):
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "scarlet-crystal-upstream-follow",
        **({"Authorization": f"Bearer {os.environ['GH_TOKEN']}"}
           if os.environ.get("GH_TOKEN") else {}),
    })
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.load(response)


def sha(value):
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise ValueError(f"Invalid immutable SHA: {str(value)[:64]}")
    return value


def pinned(text, key):
    if text.lstrip().startswith("{"):
        config = json.loads(text)
        if not isinstance(config, dict) or set(config) != {*UPSTREAMS, *SUBMODULES}:
            raise ValueError("Invalid four-key upstream source configuration")
        return sha(config[key])
    found = re.findall(r"^  " + re.escape(key) + r": ([0-9a-f]{40})$", text, re.M)
    if len(found) != 1:
        raise ValueError(f"{key}: expected one exact immutable pin; got {len(found)}")
    return sha(found[0])


def propose(text, new):
    allowed = {*UPSTREAMS, *SUBMODULES}
    if set(new) != allowed:
        raise ValueError("Refusing incomplete or unauthorized source graph update")
    if text.lstrip().startswith("{"):
        config = json.loads(text)
        if not isinstance(config, dict) or set(config) != allowed:
            raise ValueError("Invalid upstream config schema")
        for key in allowed:
            pinned(text, key)
            config[key] = sha(new[key])
        return json.dumps(config, indent=2) + "\n"
    result = text
    for key, value in new.items():
        before = pinned(result, key)
        result = result.replace(f"  {key}: {before}\n", f"  {key}: {sha(value)}\n", 1)
    return result


def discover():
    records = {}
    for key, (repository, branch) in UPSTREAMS.items():
        data = api_get(f"https://api.github.com/repos/{repository}/commits/{branch}")
        records[key] = sha(data["sha"])
    side_sha = records["EMBEDDED_SIDESTORE_REF"]
    tree = api_get(
        f"https://api.github.com/repos/LiveContainer/SideStore/git/trees/{side_sha}?recursive=1"
    )
    if tree.get("truncated"):
        raise ValueError("Upstream SideStore tree truncated; refusing automatic pin update")
    gitlinks = {entry["path"]: entry for entry in tree.get("tree", [])
                if entry.get("mode") == "160000"}
    for key, path in SUBMODULES.items():
        entry = gitlinks.get(path)
        if not entry or entry.get("type") != "commit":
            raise ValueError(f"Missing expected SideStore gitlink: {path}")
        records[key] = sha(entry["sha"])
    advisory = api_get(
        f"https://api.github.com/repos/{ADVISORY[0]}/commits/{ADVISORY[1]}"
    )
    return records, sha(advisory["sha"])


def make_report(workflow_text, found, advisory_sha):
    old = {key: pinned(workflow_text, key) for key in (*UPSTREAMS, *SUBMODULES)}
    mismatch = {key: {"current": old[key], "upstream": found[key],
                      "changed": old[key] != found[key]}
                for key in old}
    return {
        "schema": 1,
        "integration": "LiveContainer main + LiveContainerSupport fork",
        "refs": mismatch,
        "sidestore_develop_advisory": {
            "repository": ADVISORY[0], "branch": ADVISORY[1], "head": advisory_sha,
            "role": "review and forward-port changes, not a direct fork replacement"
        },
        "needs_rebase": any(entry["changed"] for entry in mismatch.values()),
        "requires": [
            "port Scarlet overlays against both upstream source trees",
            "validate Swift/Rust API and nested gitlinks",
            "all source and binary regression tests",
            "device RemotePairing handshake and install/refresh verification",
            "preserve signing credentials, app data, bundle IDs and custom UI"
        ],
        "auto_release": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--workflow", type=Path,
                             help="legacy pinned workflow source")
    input_group.add_argument("--config", type=Path,
                             help="four-key JSON source of truth; preferred")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--write", action="store_true",
                        help="stage verified source ref changes locally only")
    args = parser.parse_args(argv)
    source = args.config or args.workflow
    original = source.read_text(encoding="utf-8")
    found, advisory = discover()
    report = make_report(original, found, advisory)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.write and report["needs_rebase"]:
        candidate = propose(original, found)
        if {key: pinned(candidate, key) for key in found} != found:
            raise ValueError("Pin rewrite failed verification")
        source.write_text(candidate, encoding="utf-8")
        print("[V177_UPSTREAM] staged verified paired GitHub refs; CI/review required")
    for name, entry in report["refs"].items():
        print(f"[V177_UPSTREAM] {name} {entry['current'][:12]} -> "
              f"{entry['upstream'][:12]} changed={entry['changed']}")
    print(f"[V177_UPSTREAM] SideStore/develop advisory: {advisory[:12]}")
    print("REVIEW_REQUIRED=" + str(report["needs_rebase"]).lower())


if __name__ == "__main__":
    try:
        main()
    except (OSError, KeyError, ValueError) as exc:
        print(f"[V177_UPSTREAM] FAIL_CLOSED {exc}", file=sys.stderr)
        sys.exit(2)
