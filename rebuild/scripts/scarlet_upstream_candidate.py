#!/usr/bin/env python3
"""Scarlet Crystal upstream candidate discovery; does NOT ship or install apps.

LiveContainer main and the embedded LiveContainer/SideStore fork are the two
authoritative parents. SideStore/SideStore develop is an ADVISORY source only.
Nested SideSign/minimuxer gitlinks are read from the exact embedded fork tree.
All source SHAs are immutable, validated and staged for guarded CI.
"""
import argparse
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
FOLLOW=ROOT/"scripts/scarlet_upstream_follow.py"
spec=importlib.util.spec_from_file_location("scarlet_upstream_follow",FOLLOW)
up=importlib.util.module_from_spec(spec)
spec.loader.exec_module(up)

def candidate(pinned: dict, advisory_baseline: dict, found: dict, advisory_sha: str) -> dict:
    expected=set(up.UPSTREAMS)|set(up.SUBMODULES)
    if set(pinned)!=expected or set(found)!=expected:
        raise ValueError("Incomplete pinned upstream graph")
    for key in expected:
        up.sha(pinned[key]);up.sha(found[key])
    up.sha(advisory_sha)
    old_advisory=up.sha(advisory_baseline["sideStoreAdvisory"]["head"])
    upstream_changes={k:{"from":pinned[k],"to":found[k]} for k in sorted(expected)
                      if pinned[k]!=found[k]}
    official_changed=advisory_sha!=old_advisory
    return {
        "schema":1,
        "parentsChanged":bool(upstream_changes),
        "advisoryChanged":official_changed,
        "requiresIntegration":bool(upstream_changes) or official_changed,
        "updatedPins":found,
        "authoritativeChanges":upstream_changes,
        "sideStoreAdvisory":{
            "repository":"SideStore/SideStore",
            "branch":"develop",
            "previous":old_advisory,
            "latest":advisory_sha,
            "autoReplaceEmbeddedFork":False
        },
        "originalGlassPreserved":True,
        "appIdentityPreserved":True,
        "autoRelease":False,
        "autoDeviceInstall":False,
        "reviewRequiredForUnknownAPIDiffs":True,
        "prerequisites":[
            "match LiveContainer and fork API behavior",
            "verify pinned SideSign/minimuxer gitlinks",
            "verify unchanged original Liquid Glass implementation",
            "build iOS host with all four bundle identifiers",
            "test Apple login/2FA and installer in actual iPhone",
            "confirm existing App Groups and user data remain accessible"
        ]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--pins",type=Path,required=True)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--candidate-pins",type=Path,required=True)
    p.add_argument("--candidate-baseline",type=Path,required=True)
    args=p.parse_args()
    pins=json.loads(args.pins.read_text(encoding="utf-8"))
    old=json.loads(args.baseline.read_text(encoding="utf-8"))
    found,advisory=up.discover()
    result=candidate(pins,old,found,advisory)
    result["checkedAt"]=datetime.now(timezone.utc).isoformat()
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.candidate_pins.parent.mkdir(parents=True,exist_ok=True)
    args.candidate_baseline.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    args.candidate_pins.write_text(json.dumps(found,indent=2)+"\n",encoding="utf-8")
    if result["advisoryChanged"]:
        old["sideStoreAdvisory"]["head"]=advisory
        old["observedAt"]=result["checkedAt"]
    args.candidate_baseline.write_text(json.dumps(old,indent=2)+"\n",encoding="utf-8")
    print("SCARLET_UPSTREAM_PARENT_CHANGE="+str(result["parentsChanged"]).lower())
    print("SCARLET_SIDESTORE_ADVISORY_CHANGE="+str(result["advisoryChanged"]).lower())
    print("SCARLET_UPSTREAM_CANDIDATE="+str(result["requiresIntegration"]).lower())
    print("[NOTICE] Source updates are staged, never auto installed or published.")

if __name__=="__main__":
    main()
