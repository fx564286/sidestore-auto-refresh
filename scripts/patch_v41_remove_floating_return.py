#!/usr/bin/env python3
"""V41 UI: remove floating guest-return button; retain native host navigation."""
from pathlib import Path
import sys
P=Path("MultitaskSupport/AppSceneViewController.m")
M="NRG_V41_FLOATING_RETURN_REMOVED"
def patch(s):
    if M in s:return s
    anchor="    if (!self.lcReturnControl) {"
    replacement="    // "+M+": do not create an overlapping guest-return overlay.\n    [self.lcReturnControl removeFromSuperview];\n    self.lcReturnControl = nil;\n    return;\n"+anchor
    if s.count(anchor)!=1:raise RuntimeError("guest-return overlay anchor mismatch")
    return s.replace(anchor,replacement,1)
if __name__=="__main__":
    p=Path(sys.argv[1])/P;s=p.read_text();t=patch(s)
    if s!=t:p.write_text(t)
    assert patch(t)==t
    print("[PASS] V41 floating guest return control removed")
