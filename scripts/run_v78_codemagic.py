#!/usr/bin/env python3
"""Run the pinned V78 host/IPA workflow on Codemagic macOS (not GitHub Actions).

Replay only the first, source-and-host-build job. External checkout actions are
mapped to pinned git clones; artifact upload actions are delegated to Codemagic.
There is no automatic signing, release or app/data mutation.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import traceback

import yaml

ROOT = Path.cwd().resolve()
WORKFLOW = ROOT / ".github/workflows/livecontainer-build.yml"
EXPECTED_BRANCH = "fix/scarlet-v78-liveprocess-null-pref-cache-20261024"
SKIP_USE = ("actions/upload-artifact@", "actions/download-artifact@")
EXTERNAL_REPOS = {"idevice": "SideStore/idevice", "jktcp": "SideStore/jktcp"}


def cmd(args, cwd=ROOT):
    print("[CODEMAGIC_RUN]", " ".join(map(str, args)), flush=True)
    subprocess.run(args, cwd=cwd, env=os.environ.copy(), check=True)


def revision():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def branch():
    return (os.environ.get("CM_BRANCH") or subprocess.check_output(
        ["git", "branch", "--show-current"], text=True
    ).strip())


def configure_env(yaml_job):
    actual_branch = branch()
    if actual_branch != EXPECTED_BRANCH:
        raise RuntimeError("Wrong build branch: " + actual_branch)
    os.environ["GITHUB_SHA"] = revision()
    os.environ["GITHUB_REPOSITORY"] = "fx564286/sidestore-auto-refresh"
    os.environ["GITHUB_WORKSPACE"] = str(ROOT)
    os.environ["GITHUB_REF"] = "refs/heads/" + actual_branch
    os.environ["GITHUB_RUN_NUMBER"] = str(os.environ.get("CM_BUILD_NUMBER") or "1")
    os.environ["GITHUB_RUN_ID"] = str(os.environ.get("CM_BUILD_NUMBER") or "1")
    os.environ["RUNNER_TEMP"] = str(ROOT / ".scarlet-runner-temp")
    Path(os.environ["RUNNER_TEMP"]).mkdir(exist_ok=True)
    for k, v in yaml_job["environment"].items():
        os.environ[k] = str(v)
    print("[CODEMAGIC] branch=" + actual_branch + " sha=" + revision(), flush=True)
    print("[CODEMAGIC] unsigned archive only, signing assets unchanged", flush=True)
    cmd(["xcodebuild", "-version"])
    cmd(["xcodebuild", "-showsdks"])


def clone_checkout(step):
    with_options = step.get("with", {})
    relpath = str(with_options.get("path", "."))
    dest = ROOT / relpath
    if dest.exists():
        raise RuntimeError("Checkout destination already exists: " + str(dest))
    repo = with_options.get("repository")
    if not repo:
        # actions/checkout@v4 of the running builder. Avoid recursive copy.
        cmd(["git", "clone", "--no-hardlinks", "--no-local", str(ROOT), str(dest)])
        cmd(["git", "checkout", "--detach", os.environ["GITHUB_SHA"]], cwd=dest)
        return
    if relpath not in EXTERNAL_REPOS or repo != EXTERNAL_REPOS[relpath]:
        raise RuntimeError("Unapproved repository checkout " + str(repo))
    ref = with_options.get("ref")
    if not isinstance(ref, str):
        raise RuntimeError("Pinned checkout ref absent for " + relpath)
    ref = interpolate(ref, os.environ)
    cmd(["git", "clone", "--filter=blob:none", "--no-checkout",
         "https://github.com/" + repo + ".git", str(dest)])
    cmd(["git", "fetch", "--no-tags", "--depth=1", "origin", ref], cwd=dest)
    cmd(["git", "checkout", "--detach", "FETCH_HEAD"], cwd=dest)
    if with_options.get("submodules") in ("recursive", True):
        cmd(["git", "submodule", "update", "--init", "--recursive", "--depth=1"], cwd=dest)


def interpolate(value, env):
    # GitHub Actions expression substitution is intentionally allowlisted.
    if not isinstance(value, str):
        return str(value)
    pattern = re.compile(r"\$\{\{\s*([^}]+?)\s*\}\}")
    def sub(match):
        key = match.group(1).strip()
        if key == "github.workspace":
            return str(ROOT)
        if key.startswith("env."):
            name = key[4:]
            if name not in env:
                raise RuntimeError("Unknown workflow expression " + key)
            return env[name]
        raise RuntimeError("Unmapped workflow expression: " + key)
    return pattern.sub(sub, value)


def run_step(step):
    name = step.get("name", "unnamed")
    print("\n[CODEMAGIC_STEP] " + name, flush=True)
    if "uses" in step:
        action = step["uses"]
        if action.startswith("actions/checkout@"):
            clone_checkout(step)
        elif action.startswith(SKIP_USE):
            print("[CODEMAGIC_STEP] artifact transfer handled by Codemagic", flush=True)
        elif action.startswith("maxim-lobanov/setup-xcode@"):
            print("[CODEMAGIC_STEP] Xcode selected by codemagic.yaml", flush=True)
        else:
            raise RuntimeError("Unmapped external action " + action)
        return
    if "run" not in step:
        raise RuntimeError("Action has no run/uses: " + name)
    subenv = os.environ.copy()
    subenv.update({k: interpolate(v, subenv) for k, v in (step.get("env") or {}).items()})
    workdir = ROOT / interpolate(step.get("working-directory", "."), subenv)
    if not workdir.is_dir():
        raise RuntimeError("Missing working directory: " + str(workdir))
    script = interpolate(step["run"], subenv)
    # Original CI shells use pipefail for essential build stages.
    subprocess.run(["bash", "-e", "-o", "pipefail", "-c", script],
                   env=subenv, cwd=workdir, check=True)


def main():
    config = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = config["jobs"]["source-and-host-build"]
    # GitHub YAML 1.1 'on' parsing is irrelevant: only the pinned job runs.
    configure_env({"environment": config["env"]})
    steps = job["steps"]
    failure = None
    for step in steps:
        cond = str(step.get("if", "")).strip()
        if "false" in cond.lower() and "always" not in cond:
            print("[CODEMAGIC] skipped optional step: " + step.get("name", ""), flush=True)
            continue
        if failure is not None and "always" not in cond:
            continue
        try:
            run_step(step)
        except Exception as exc:
            if failure is None:
                failure = exc
            print("[CODEMAGIC_ERROR] " + step.get("name", "unnamed") + ": " + repr(exc),
                  flush=True)
            traceback.print_exc()
    if failure is not None:
        raise RuntimeError("V78 external build failed; inspect Codemagic logs/artifacts") from failure
    expected = ROOT / "artifacts/LiveContainer-SideStore-v3.0.3-rc.ipa"
    if not expected.is_file():
        raise RuntimeError("Build steps finished but verified IPA does not exist")
    print("[CODEMAGIC_PASS] unsigned IPA exists: " + str(expected), flush=True)


if __name__ == "__main__":
    main()
