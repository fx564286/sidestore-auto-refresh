#!/usr/bin/env python3
"""Track the exact upstream source graph used by Scarlet Crystal, without merging.

GitHub Action checks the LiveContainer engine and its maintained SideStore fork
plus the SideSign/minimuxer gitlinks owned by THAT fork's commit.
Never directly replace the maintained fork with SideStore/develop.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import urllib.request

OWNER_REPOS = {
    "LIVE_CONTAINER_REF": ("LiveContainer/LiveContainer", "main"),
    "EMBEDDED_SIDESTORE_REF": ("LiveContainer/SideStore", "LiveContainerSupport"),
}
GITLINKS = {
    "MINIMUXER_REF": "Dependencies/minimuxer",
    "SIDESIGN_REF": "Dependencies/SideSign",
}
ADVISORY_REPO_BRANCH = ("SideStore/SideStore", "develop")
KEYS = set(OWNER_REPOS) | set(GITLINKS)
PATTERN = re.compile(r"[0-9a-f]{40}\Z")


def validated_pin(value):
    if not isinstance(value, str) or not PATTERN.fullmatch(value):
        raise ValueError("Invalid immutable upstream commit SHA")
    return value


def decode_pins(raw):
    p = json.loads(raw)
    if not isinstance(p, dict) or set(p) != KEYS:
        raise ValueError("Incomplete or unknown upstream pin keys")
    return {k: validated_pin(v) for k, v in p.items()}


def github_api(url):
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "scarlet-crystal-rebuild-upstream"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def discover(api=github_api):
    next_pins = {}
    for key, (repo, branch) in OWNER_REPOS.items():
        result = api(f"https://api.github.com/repos/{repo}/commits/{branch}")
        next_pins[key] = validated_pin(result["sha"])

    side_sha = next_pins["EMBEDDED_SIDESTORE_REF"]
    tree = api(f"https://api.github.com/repos/LiveContainer/SideStore/git/trees/{side_sha}?recursive=1")
    if tree.get("truncated") or not isinstance(tree.get("tree"), list):
        raise ValueError("Invalid or truncated embedded SideStore source tree")
    links = {item["path"]: item for item in tree["tree"] if item.get("mode") == "160000"}
    for key, path in GITLINKS.items():
        item = links.get(path)
        if not item or item.get("type") != "commit":
            raise ValueError("Expected gitlink absent in pinned embedded SideStore: " + path)
        next_pins[key] = validated_pin(item["sha"])

    repo, branch = ADVISORY_REPO_BRANCH
    advisory = validated_pin(api(f"https://api.github.com/repos/{repo}/commits/{branch}")["sha"])
    return next_pins, advisory


def make_report(current, latest, advisory):
    if set(current) != KEYS or set(latest) != KEYS:
        raise ValueError("Cannot compare partial source graphs")
    return {
        "schema": 1,
        "base": "LiveContainer main + LiveContainer maintained SideStore fork",
        "refs": {
            key: {
                "pinned": current[key],
                "observed": latest[key],
                "changed": current[key] != latest[key]
            } for key in sorted(KEYS)
        },
        "advisory_sidestore_develop": advisory,
        "needs_review": any(current[k] != latest[k] for k in KEYS),
        "automated_source_detection": True,
        "automatic_unreviewed_release": False,
        "requires": [
            "pin atomically all four source references",
            "validate embedded SideSign and minimuxer compatibility",
            "compare existing native Liquid Glass implementation and gestures",
            "compile full real iOS host and four extensions",
            "verify provisioning, pairing, login, 2FA, guest runtime, UI and data",
            "publish only after all release gates pass",
        ]
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pins", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    args = ap.parse_args(argv)

    current = decode_pins(args.pins.read_text(encoding="utf8"))
    latest, advisory = discover()
    report = make_report(current, latest, advisory)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+"\n", encoding="utf8")
    # Produces an atomic new four-pin candidate; safe to stage in a review PR.
    # No source trees, signing assets or app data are modified here.
    args.candidate.parent.mkdir(parents=True, exist_ok=True)
    args.candidate.write_text(json.dumps(latest, indent=2)+"\n", encoding="utf8")
    print("[UPSTREAM]", "change_detected" if report["needs_review"] else "unchanged")
    for k, v in report["refs"].items():
        print("[PIN]", k, v["pinned"][:12], "->", v["observed"][:12],
              "changed="+str(v["changed"]).lower())
    print("[NOTICE] No auto-merge, release, signing or iPhone installation")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as exc:
        print("[STOP] upstream source graph verification failed:", exc, file=sys.stderr)
        sys.exit(2)
