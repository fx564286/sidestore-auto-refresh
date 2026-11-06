#!/usr/bin/env python3
"""New-project source tracker. No V-series dependencies or old patch scripts."""
from __future__ import annotations
import argparse
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

UPSTREAMS={
    "LIVE_CONTAINER_REF":("LiveContainer/LiveContainer","main"),
    "EMBEDDED_SIDESTORE_REF":("LiveContainer/SideStore","LiveContainerSupport")
}
SUBMODULES={
    "MINIMUXER_REF":"Dependencies/minimuxer",
    "SIDESIGN_REF":"Dependencies/SideSign"
}
ADVISORY=("SideStore/SideStore","develop")
SHA_RE=re.compile(r"^[0-9a-f]{40}$")

def sha(s:str)->str:
    if not isinstance(s,str) or not SHA_RE.fullmatch(s):
        raise ValueError("Invalid 40-character immutable git SHA")
    return s

def get_json(url:str)->dict:
    headers={
        "Accept":"application/vnd.github+json",
        "User-Agent":"ScarletCrystalCleanUpstream"
    }
    token=os.getenv("GH_TOKEN")
    if token:headers["Authorization"]="Bearer "+token
    req=urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req,timeout=25) as response:
        return json.load(response)

def discover()->tuple[dict,str]:
    found={}
    for key,(repo,branch) in UPSTREAMS.items():
        data=get_json(f"https://api.github.com/repos/{repo}/commits/{branch}")
        found[key]=sha(data["sha"])
    target=found["EMBEDDED_SIDESTORE_REF"]
    source=get_json(f"https://api.github.com/repos/LiveContainer/SideStore/git/trees/{target}?recursive=1")
    if source.get("truncated"):raise ValueError("Embedded fork source tree truncated")
    links={e.get("path"):e for e in source.get("tree",[]) if e.get("mode")=="160000"}
    for key,path in SUBMODULES.items():
        e=links.get(path)
        if e is None or e.get("type")!="commit":
            raise ValueError("Embedded SideStore missing gitlink: "+path)
        found[key]=sha(e["sha"])
    advisory=sha(get_json(f"https://api.github.com/repos/{ADVISORY[0]}/commits/{ADVISORY[1]}")["sha"])
    return found,advisory

def candidate(pinned:dict,advisory_baseline:dict,found:dict,advisory_sha:str)->dict:
    expected=set(UPSTREAMS)|set(SUBMODULES)
    if set(pinned)!=expected or set(found)!=expected:
        raise ValueError("Refuse partial parent + nested SideSign source graph")
    for k in expected:sha(pinned[k]);sha(found[k])
    sha(advisory_sha)
    old=sha(advisory_baseline["sideStoreAdvisory"]["head"])
    changes={k:{"from":pinned[k],"to":found[k]} for k in sorted(expected) if pinned[k]!=found[k]}
    advisoryChanged=advisory_sha!=old
    return {
        "schema":1,"parentsChanged":bool(changes),"advisoryChanged":advisoryChanged,
        "requiresIntegration":bool(changes) or advisoryChanged,"updatedPins":found,
        "authoritativeChanges":changes,
        "sideStoreAdvisory":{"repository":ADVISORY[0],"branch":ADVISORY[1],
            "previous":old,"latest":advisory_sha,"autoReplaceEmbeddedFork":False},
        "originalGlassPreserved":True,"appIdentityPreserved":True,
        "autoRelease":False,"autoDeviceInstall":False,
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

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--pins",type=Path,required=True)
    p.add_argument("--baseline",type=Path,required=True)
    p.add_argument("--report",type=Path,required=True)
    p.add_argument("--candidate-pins",type=Path,required=True)
    p.add_argument("--candidate-baseline",type=Path,required=True)
    a=p.parse_args()
    current=json.loads(a.pins.read_text())
    baseline=json.loads(a.baseline.read_text())
    found,advisory=discover()
    result=candidate(current,baseline,found,advisory)
    result["checkedAt"]=datetime.now(timezone.utc).isoformat()
    for path in [a.report,a.candidate_pins,a.candidate_baseline]:
        path.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,indent=2)+"\n")
    a.candidate_pins.write_text(json.dumps(found,indent=2)+"\n")
    if result["advisoryChanged"]:
        baseline["sideStoreAdvisory"]["head"]=advisory
        baseline["observedAt"]=result["checkedAt"]
    a.candidate_baseline.write_text(json.dumps(baseline,indent=2)+"\n")
    print("SCARLET_UPSTREAM_PARENT_CHANGE="+str(result["parentsChanged"]).lower())
    print("SCARLET_SIDESTORE_ADVISORY_CHANGE="+str(result["advisoryChanged"]).lower())
    print("[INFO] Source candidate only; no automatic release or device install.")

if __name__=="__main__":
    main()
