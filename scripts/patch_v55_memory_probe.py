#!/usr/bin/env python3
"""V55 observational memory telemetry; never manufactures Apple entitlements.

Applies after V48 probe, logs active host/LiveProcess physical footprint and
whether the kernel task_info call succeeded. Independent of guest IPA claims.
"""
from pathlib import Path
import sys
TARGET=Path("LiveContainer/LCBootstrap.m")
MARK="NRG_V55_MEMORY_FOOTPRINT"

def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or "phys_footprint_mb=%llu" not in s:
            raise RuntimeError("partial V55 memory probe")
        return s
    if "NRG_V48_GUEST_RUNTIME_CAPABILITIES" not in s:
        raise RuntimeError("V55 memory telemetry requires V48 capability probe")
    old="#include <sys/proc.h>\n"
    if s.count(old)!=1: raise RuntimeError("missing V48 sys/proc header")
    s=s.replace(old,old+"#include <mach/task_info.h>\n",1)
    old='    int va = nrgV48EntitlementBool(CFSTR("com.apple.developer.kernel.extended-virtual-addressing"));\n'
    new=old+"""    // """+MARK+""": measured footprint is NOT an entitlement grant.
    task_vm_info_data_t vmInfo = {0};
    mach_msg_type_number_t vmCount = TASK_VM_INFO_COUNT;
    kern_return_t vmStatus = task_info(mach_task_self(), TASK_VM_INFO,
                                       (task_info_t)&vmInfo, &vmCount);
    unsigned long long footprintMB = vmStatus == KERN_SUCCESS
        ? (unsigned long long)(vmInfo.phys_footprint / (1024ULL * 1024ULL)) : 0ULL;
"""
    if s.count(old)!=1: raise RuntimeError("missing V48 entitlement probe")
    s=s.replace(old,new,1)
    old='''          "jit_pool_unverified=1", stage, getpid(), isLiveProcess,
          csResult, debugged, csAllow, traced, taskAllow, memory, va);'''
    new='''          "jit_pool_unverified=1 phys_footprint_mb=%llu footprint_valid=%d",
          stage, getpid(), isLiveProcess, csResult, debugged, csAllow,
          traced, taskAllow, memory, va, footprintMB, vmStatus == KERN_SUCCESS);'''
    if s.count(old)!=1: raise RuntimeError("missing V48 log call")
    return s.replace(old,new,1)

def main(root):
    p=root/TARGET
    old=p.read_text()
    new=patch(old)
    if patch(new)!=new: raise RuntimeError("V55 memory probe non-idempotent")
    if old!=new:p.write_text(new)
    print("[PASS] V55 memory footprint telemetry, no entitlement changes")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v55_memory_probe.py <LiveContainer>")
    main(Path(sys.argv[1]))
