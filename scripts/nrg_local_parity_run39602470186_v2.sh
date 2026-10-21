#!/usr/bin/env bash
# Reproduce the SOURCE CHECKS AND PATCH stage of GitHub Actions #39602470186.
# Does not sign/install IPA or touch Apple accounts, iPhone, or original NRG.
set -Eeuo pipefail
umask 077

BUILDER=55b2ecdcc8485e5903fcdb27a677581dbfd7ad5a
LC=12377cf3b91d51739a33f14a302e5f522b238593
SS=ff25922e5c13ccfafd83bda5092910d848ebd409
MINIMUXER=98c3c79982f813878e922ab42f9545314a700f0c
SIDESIGN=a731c0d5a9a6617c7b385ae493e07ffb7f81cd5d
IDEVICE=ebd7dadfc55d1c4facee3d11ecf5b28e20548b57
JKTCP=e674e1eee6d5943e13b1eba0bd24a9dd0b2fa020

BASE="$HOME/NRG-Tools/nrg-local-run39602470186-v2"
mkdir -p "$BASE/work" "$BASE/logs" "$BASE/artifacts/logs"
cd "$BASE"
exec > >(tee -a "$BASE/logs/local-parity.log") 2>&1
fail() { echo "[FAIL] $*" >&2; exit 1; }
trap 'ret=$?; if [ "$ret" -ne 0 ]; then echo "[FAIL] Check $BASE/logs for details (exit=$ret)" >&2; fi' EXIT
for command_name in git python3 swiftc; do
  command -v "$command_name" >/dev/null || fail "$command_name is missing"
done

pin() {
  local url="$1" path="$2" sha="$3"
  if [ ! -d "$path/.git" ]; then
    git clone -q --depth=1 --filter=blob:none --no-checkout "$url" "$path"
  fi
  if ! git -C "$path" cat-file -e "$sha^{commit}" 2>/dev/null; then
    git -C "$path" fetch -q --depth=1 origin "$sha"
  fi
  if [ "$(git -C "$path" rev-parse HEAD)" != "$sha" ]; then
    git -C "$path" checkout -q --detach "$sha"
  fi
  test "$(git -C "$path" rev-parse HEAD)" = "$sha" || fail "PIN mismatch $path"
  printf '[PASS] PIN %-24s %s\n' "$path" "$sha"
}

echo "=== GITHUB RUN 39602470186 SOURCE SYNC ==="
pin https://github.com/fx564286/sidestore-auto-refresh.git builder "$BUILDER"
pin https://github.com/LiveContainer/LiveContainer.git work/LiveContainer "$LC"
pin https://github.com/LiveContainer/SideStore.git work/EmbeddedSideStore "$SS"
pin https://github.com/SideStore/idevice.git idevice "$IDEVICE"
pin https://github.com/SideStore/jktcp.git jktcp "$JKTCP"

if [ ! -f "$BASE/.patch-success" ]; then
  git -C work/LiveContainer submodule update --init --recursive --depth 1
  git -C work/EmbeddedSideStore submodule update --init --recursive --depth 1
  git -C idevice submodule update --init --recursive --depth 1
  git -C jktcp submodule update --init --recursive --depth 1
fi

test "$(git -C work/EmbeddedSideStore/Dependencies/minimuxer rev-parse HEAD)" = "$MINIMUXER" || fail "minimuxer SHA mismatch"
test "$(git -C work/EmbeddedSideStore/Dependencies/SideSign rev-parse HEAD)" = "$SIDESIGN" || fail "SideSign SHA mismatch"

export LIVE_CONTAINER_TEST_SOURCE="$BASE/work/LiveContainer"
export SIDESTORE_TEST_SOURCE="$BASE/work/EmbeddedSideStore"
export EMBEDDED_SIDESTORE_TEST_SOURCE="$BASE/work/EmbeddedSideStore"
export SIDESIGN_TEST_SOURCE="$BASE/work/EmbeddedSideStore/Dependencies/SideSign"
export SIDESTORE_070_TEST_SOURCE="$BASE/work/EmbeddedSideStore"
export EMBEDDED_SIDESTORE_REF="$SS"
export LIVE_CONTAINER_REF="$LC"
unset REQUIRE_SWIFT_070_CHECKS REQUIRE_PINNED_SOURCE_CLASSIFIER_TEST || true

if [ -f "$BASE/.patch-success" ]; then
  echo "[PASS] PREVIOUS_PATCH_SUCCESS=YES"
  echo "SOURCE_ROOT=$BASE"
  exit 0
fi

echo "=== REPOSITORY TESTS: Linux Swift / Darwin API classification ==="
cat > "$BASE/linux_test_discovery.py" <<'PY'
import shutil, subprocess, tempfile, sys, unittest
from pathlib import Path
base=Path(__file__).resolve().parent
compiler=shutil.which("swiftc")
def supported(source):
    if not compiler: return False
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/"test.swift"
        p.write_text(source)
        try:
            r=subprocess.run([compiler,"-typecheck",str(p)],capture_output=True,text=True,timeout=30)
            return r.returncode==0
        except (OSError,subprocess.TimeoutExpired):
            return False
deferred={}
if sys.platform=="linux":
    if not supported("import CoreData\n"):
        deferred["test_pipeline_persistence_contract.PipelinePersistenceContractTests.test_persistence_failure_survives_upstream_error_mapping_and_refresh_verification"]="CoreData is macOS-only"
    if not supported('import Foundation\nlet _ = FileManager.default.containerURL(forSecurityApplicationGroupIdentifier: "group.test")\n'):
        deferred["test_refresh_result_bridge.RefreshResultBridgeTests.test_host_result_import_executes"]="Apple App Group API is unavailable on Linux"
suite=unittest.TestLoader().discover(str(base/"builder/tests"),pattern="test_*.py",top_level_dir=str(base/"builder/tests"))
def walk(t):
    for x in t:
        if isinstance(x,unittest.TestSuite): yield from walk(x)
        else: yield x
found=set()
for t in walk(suite):
    name=t.id()
    if name in deferred:
        found.add(name)
        original=getattr(t.__class__,t._testMethodName)
        setattr(t.__class__,t._testMethodName,unittest.skip(deferred[name])(original))
        print("DEFERRED_MACOS_ONLY="+name,flush=True)
assert found==set(deferred),(found,set(deferred))
result=unittest.TextTestRunner(verbosity=2).run(suite)
print("TESTS_RAN=",result.testsRun,"SKIPPED=",len(result.skipped),
      "FAILURES=",len(result.failures),"ERRORS=",len(result.errors),flush=True)
print("DARWIN_TESTS_NOT_VERIFIED_ON_LINUX=YES",flush=True)
sys.exit(0 if result.wasSuccessful() else 1)
PY
python3 "$BASE/linux_test_discovery.py" 2>&1 | tee "$BASE/logs/repository-tests.log"

echo "=== REPLAY PINNED GITHUB HOST PATCH STAGE ==="
python3 - "$BASE/builder/.github/workflows/livecontainer-build.yml" "$BASE/linux-host-parity.sh" <<'PY'
from pathlib import Path
import re,sys
lines=Path(sys.argv[1]).read_text().splitlines()
idx=next(i for i,s in enumerate(lines) if s.strip()=="- name: Apply and verify host integration")
start=next(i for i in range(idx+1,len(lines)) if lines[i].strip()=="run: |")
indent=len(lines[start])-len(lines[start].lstrip())+2
body=[]
for line in lines[start+1:]:
    if line.strip() and len(line)-len(line.lstrip(" "))<indent: break
    body.append(line[indent:] if line.strip() else "")
script="\n".join(body)+"\n"
for required in ["patch_v192_startup.py","patch_v60_island_guest_switch.py",
                 "patch_v58_fullscreen.py","patch_combined_service_startup.py"]:
    assert required in script,required
script,n=re.subn(r'(?m)^\s*clang -fsyntax-only -x objective-c[^\n]* \|\| \{\n(?:[^\n]*\n)*?\s*\}',
    '  echo "[DEFERRED] iPhoneOS Objective-C SDK check must run in macOS Xcode"',script)
assert n==1,n
script=script.replace("plutil -lint work/LiveContainer/LiveContainer/Info.plist",
    "python3 -c 'import plistlib; from pathlib import Path; plistlib.loads(Path(\"work/LiveContainer/LiveContainer/Info.plist\").read_bytes())'")
script=script.replace("plutil -extract BGTaskSchedulerPermittedIdentifiers.0 raw work/LiveContainer/LiveContainer/Info.plist",
    "python3 -c 'import plistlib; from pathlib import Path; p=plistlib.loads(Path(\"work/LiveContainer/LiveContainer/Info.plist\").read_bytes()); assert p.get(\"BGTaskSchedulerPermittedIdentifiers\")'")
assert "plutil -" not in script and "xcrun --sdk" not in script
Path(sys.argv[2]).write_text("#!/usr/bin/env bash\n"+script)
print("[PASS] Exact host patch order extracted from pinned workflow")
PY

bash -n "$BASE/linux-host-parity.sh"
bash "$BASE/linux-host-parity.sh" 2>&1 | tee "$BASE/logs/host-patches.log"
git -C work/LiveContainer diff --stat > "$BASE/logs/LiveContainer-diffstat.txt"
git -C work/EmbeddedSideStore diff --stat > "$BASE/logs/SideStore-diffstat.txt"
test -s "$BASE/logs/LiveContainer-diffstat.txt" || fail "Missing LiveContainer patch evidence"
test -s "$BASE/logs/SideStore-diffstat.txt" || fail "Missing SideStore patch evidence"

date -u +%Y%m%dT%H%M%SZ > "$BASE/.patch-success"
echo "[PASS] LINUX_SOURCE_TESTS_AND_HOST_PATCHES=YES"
echo "MACOS_XCODE_IPA_BUILD=NOT_EXECUTED"
echo "APPLE_CERTIFICATES_AND_ORIGINAL_NRG_UNCHANGED=YES"
echo "SOURCE_ROOT=$BASE"
echo "LOG_DIRECTORY=$BASE/logs"
