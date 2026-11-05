#!/usr/bin/env python3
"""Scarlet iOS Shortcut -> GitHub workflow_dispatch -> local CachyOS signer.

The GitHub-hosted workflow only records the request. This agent continuously
checks workflow_dispatch runs. Only requests triggered by owner fx564286
can run the existing verified local PEM signer. All signing keys stay local.
Nothing is triggered by timer; no inbound NAS / SSH ports on phone or PC.
"""
from __future__ import annotations
import base64
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO="fx564286/sidestore-auto-refresh"
OWNER="fx564286"
WORKFLOW="scarlet-sign-request.yml"
ROOT=Path.home()/".local/share/scarlet-crystal/latest-publisher"
PUBLISHER=ROOT/"latest.py"
PUBLISHER_PIN="https://raw.githubusercontent.com/fx564286/sidestore-auto-refresh/66e33659c0af590be16089aa8889fb1541d840a6/tools/scarlet_latest_publish.py"
STATE=Path.home()/".local/state/scarlet-crystal-shortcut-sign"
LAST=STATE/"last-processed.json"
STATUS_FILE="scarlet-sign-status.json"
INSTALL_URL="https://fx564286.github.io/sidestore-auto-refresh/scarlet-latest.html"
POLL_SECONDS=25

def message(*args):
    print(*args,file=sys.stderr,flush=True)

def timestamp():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def command(args,timeout=1800):
    p=subprocess.run([str(v) for v in args],capture_output=True,text=True,
                     errors="replace",timeout=timeout)
    if p.returncode:
        raise RuntimeError("COMMAND_FAILED "+str(args[:3])+" exit="+str(p.returncode)+
                           " "+(p.stderr or p.stdout)[-900:])
    return p.stdout

def gh(path, method="GET", data=None):
    args=["gh","api","--method",method,"repos/"+REPO+"/"+path]
    if data is None:
        return json.loads(command(args,timeout=40))
    with tempfile.NamedTemporaryFile("w",encoding="utf8",delete=False) as file:
        json.dump(data,file)
        temp=Path(file.name)
    try:
        return json.loads(command(args+["--input",str(temp)],timeout=50))
    finally:
        temp.unlink(missing_ok=True)

def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    candidate=path.with_name(path.name+".tmp."+str(os.getpid()))
    try:
        candidate.write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2))
        candidate.chmod(0o600)
        candidate.replace(path)
    finally:
        candidate.unlink(missing_ok=True)

def publish_status(run_id,state,summary):
    data={"request_run_id":run_id,"status":state,"message":summary,
          "updated_at":timestamp(),"install_url":INSTALL_URL,
          "phone_install_verified":False}
    # Publish only nonsecret process state; signing keys never leave PC.
    raw=(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
    key="contents/"+STATUS_FILE
    old=gh(key+"?ref=gh-pages")
    if not isinstance(old,dict):
        raise RuntimeError("PAGES_STATUS_REFERENCE_INVALID")
    payload={"branch":"gh-pages","message":"Update iOS-triggered Scarlet signing status",
             "sha":old["sha"],"content":base64.b64encode(raw).decode()}
    gh(key,method="PUT",data=payload)

def ensure_publisher():
    if not PUBLISHER.is_file():
        ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
        with urllib.request.urlopen(PUBLISHER_PIN,timeout=25) as req:
            data=req.read(1000000)
        if not data.startswith(b"#!/usr/bin/env python3") or len(data)<10000:
            raise RuntimeError("PINNED_PUBLISHER_DOWNLOAD_INVALID")
        with tempfile.NamedTemporaryFile("wb",dir=ROOT,delete=False) as f:
            temp=Path(f.name);f.write(data)
        try:
            command(["python3","-m","py_compile",temp],timeout=30)
            temp.chmod(0o600)
            temp.replace(PUBLISHER)
        finally:
            temp.unlink(missing_ok=True)
    # Existing approved key and certificate must be on this PC.
    base=Path.home()/".local/share/scarlet-crystal"
    for name in ["signing/identity-v188-enrolled/private-key.pem",
                 "signing/identity-v188-enrolled/certificate.pem",
                 "v188-signed/sign-v188.py"]:
        if not (base/name).is_file():
            raise RuntimeError("SIGNING_DEPENDENCY_MISSING:"+name)

def accepted(run):
    return (run.get("event")=="workflow_dispatch" and
            run.get("head_branch")=="main" and
            (run.get("actor") or {}).get("login","").lower()==OWNER.lower() and
            (run.get("head_repository") or {}).get("full_name")==REPO and
            run.get("path") in (".github/workflows/"+WORKFLOW, ".github/workflows/"+WORKFLOW+"@main"))

def latest_request():
    records=gh("actions/workflows/"+WORKFLOW+"/runs?event=workflow_dispatch&per_page=30")
    requests=[r for r in records.get("workflow_runs",[]) if isinstance(r.get("id"),int)]
    if not requests:
        return None
    # Only the latest signed owner request matters; no duplicate sign cycles.
    return max(requests,key=lambda r:r["id"])

def once():
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    previous=json.loads(LAST.read_text()).get("last_id",0) if LAST.is_file() else 0
    run=latest_request()
    if run is None or run["id"]<=previous:
        return
    request_id=run["id"]
    if not accepted(run):
        message("[SKIP] REQUEST_NOT_OWNER_APPROVED",request_id)
        write_json(LAST,{"last_id":request_id,"status":"rejected","at":timestamp()})
        return
    message("[REQUEST] SHORTCUT_SIGN_REQUEST_ACCEPTED",request_id)
    try:
        publish_status(request_id,"running","아이폰 단축어 서명 요청을 PC에서 처리 중이야.")
    except Exception as e:
        message("[WARN] STATUS_PUBLISH_FAILED",type(e).__name__)
    try:
        ensure_publisher()
        output=command(["python3",PUBLISHER],timeout=1800)
        link=output.strip().splitlines()[-1] if output.strip() else ""
        if link != INSTALL_URL:
            raise RuntimeError("PUBLISHER_DID_NOT_RETURN_APPROVED_INSTALL_URL")
        message("[PASS] LOCAL_APPLE_SIGNING_PUBLISH_COMPLETE",request_id)
        try:
            publish_status(request_id,"published","서명 IPA 게시가 완료됐어. 아이폰 설치는 별도 확인이 필요해.")
        except Exception:
            message("[WARN] FINAL_STATUS_PUBLICATION_FAILED")
        write_json(LAST,{"last_id":request_id,"status":"published","at":timestamp()})
    except Exception as e:
        message("[STOP] LOCAL_SIGNING_FAILED",request_id,type(e).__name__,str(e)[:450])
        try:
            publish_status(request_id,"failed","로컬 서명 또는 게시 실패. PC의 서비스 로그를 확인해야 해.")
        except Exception:
            message("[WARN] FAILURE_STATUS_PUBLICATION_FAILED")
        write_json(LAST,{"last_id":request_id,"status":"failed","at":timestamp()})

def main():
    if os.geteuid()==0:
        raise RuntimeError("NEVER_RUN_SIGNER_AS_ROOT")
    command(["gh","auth","status"],timeout=15)
    STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
    message("[START] GITHUB_REQUEST_RELAY_POLLING",POLL_SECONDS)
    while True:
        try:
            once()
        except Exception as e:
            message("[ERROR] POLL",type(e).__name__,str(e)[:350])
        time.sleep(POLL_SECONDS)

if __name__=="__main__":
    try:main()
    except KeyboardInterrupt:sys.exit(130)
    except Exception as e:
        message("[STOP]",type(e).__name__,str(e)[:600])
        sys.exit(2)
