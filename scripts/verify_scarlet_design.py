#!/usr/bin/env python3
"""Fail closed if Scarlet Crystal's user-authored UI has been replaced by stock UI.

Source proof only: an on-device test is still required to establish the effect,
rotation, long-press and touch interactions actually work. No user files or
signing material are changed by this tool.
"""
import argparse
import json
from pathlib import Path
import sys

def check(root, contract):
    if contract.get("schema") != 1 or contract.get("product") != "Scarlet Crystal":
        raise ValueError("unrecognized product design contract")
    requirements = contract.get("requirements")
    if not isinstance(requirements, list) or len(requirements) < 6:
        raise ValueError("missing required user-authored design checks")
    results = []
    seen = set()
    for item in requirements:
        key, relative, markers = item["key"], item["path"], item["all"]
        if key in seen:
            raise ValueError(f"duplicate UI feature: {key}")
        seen.add(key)
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"unsafe source path for UI proof: {relative}")
        p = root / relative_path
        valid_source = p.is_file() and not p.is_symlink()
        src = p.read_text(encoding="utf-8") if valid_source else ""
        if not isinstance(markers, list) or not markers:
            raise ValueError(f"invalid UI feature markers: {key}")
        missing = [marker for marker in markers if not isinstance(marker, str)
                   or not marker.startswith("SCARLET_V") or marker not in src]
        results.append({"feature": key, "source": relative, "source_exists": valid_source,
                        "missing": missing, "pass": valid_source and not missing})
    return {
        "schema": 1,
        "product": "Scarlet Crystal",
        "user_authored_design_source_preserved": all(v["pass"] for v in results),
        "runtime_design_verified": False,
        "can_publish_as_design_preserved": all(v["pass"] for v in results),
        "checks": results,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--contract", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    contract = json.loads(args.contract.read_text(encoding="utf-8"))
    report = check(args.source.resolve(), contract)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    for check_result in report["checks"]:
        status = "PASS" if check_result["pass"] else "FAIL"
        print(f"[SCARLET_DESIGN] {status} {check_result['feature']}: "
              f"missing={','.join(check_result['missing']) or '-'}")
    if not report["user_authored_design_source_preserved"]:
        raise SystemExit("[SCARLET_DESIGN] FAIL_CLOSED: existing Scarlet Crystal visual design "
                         "is absent. Do NOT publish as a completed fork.")
    print("[SCARLET_DESIGN] source invariants present; device UI still unverified")

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError) as e:
        print(f"[SCARLET_DESIGN] FAIL_CLOSED: {e}", file=sys.stderr)
        sys.exit(2)
