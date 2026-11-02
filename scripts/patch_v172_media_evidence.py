#!/usr/bin/env python3
"""V172 safe in-process media failure evidence without altering AVPlayer behavior.

On some iOS hosted guests AVPlayer errors are not written to SideStore logs.
Observe the public NSNotification names on visible guest scenes. No URL,
audio session identity, filenames, video data, permissions or private APIs.
"""
from pathlib import Path
import sys
FILE=Path("MultitaskSupport/DecoratedAppSceneViewController.m")
MARK="SCARLET_V172_MEDIA_EVIDENCE"
OLD='''    _appSceneVC = [[AppSceneViewController alloc] initWithBundleId:bundleId dataUUID:dataUUID delegate:self];'''
NEW='''    _appSceneVC = [[AppSceneViewController alloc] initWithBundleId:bundleId dataUUID:dataUUID delegate:self];
    // SCARLET_V172_MEDIA_EVIDENCE: only observe, never seize audio sessions
    // or force a guest player's state; media failures must be diagnosed
    // separately from device pairing and rotation.
    for (NSString *eventName in @[
        @"AVPlayerItemFailedToPlayToEndTimeNotification",
        @"AVPlayerItemPlaybackStalledNotification",
        @"AVPlayerItemNewErrorLogEntryNotification",
        @"AVAudioSessionInterruptionNotification"
    ]) {
        [[NSNotificationCenter defaultCenter] addObserver:self
            selector:@selector(nrgV172MediaEvent:) name:eventName object:nil];
    }'''
HOOK='''- (instancetype)initWindowName:(NSString*)windowName bundleId:(NSString*)bundleId dataUUID:(NSString*)dataUUID rootVC:(UIViewController*)rootVC {'''
METHOD='''// A diagnostic only: no playback interception, private player hooks or
// per-application exemptions. Never log notification payloads or content URLs.
- (void)nrgV172MediaEvent:(NSNotification *)note {
    NSString *event = note.name;
    NSString *type = [event isEqualToString:@"AVPlayerItemFailedToPlayToEndTimeNotification"]
        ? @"item_failed" :
        ([event isEqualToString:@"AVPlayerItemPlaybackStalledNotification"] ? @"stalled" :
        ([event isEqualToString:@"AVPlayerItemNewErrorLogEntryNotification"] ? @"error_log" : @"audio_interrupted"));
    NSError *error = [note.userInfo[@"AVPlayerItemFailedToPlayToEndTimeErrorKey"] isKindOfClass:NSError.class]
        ? note.userInfo[@"AVPlayerItemFailedToPlayToEndTimeErrorKey"] : nil;
    NSInteger code = error ? error.code : 0;
    dispatch_async(dispatch_get_main_queue(), ^{
        if (!self.view.window || self.view.hidden || !self.appSceneVC.isAppRunning) return;
        NSLog(@"[SCARLET_V172_MEDIA] event=%@ error_code=%ld content=redacted",
              type, (long)code);
    });
}
- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

'''
def patch(s):
    if MARK in s:
        if s.count(MARK)!=1 or s.count("nrgV172MediaEvent:")!=2:
            raise ValueError("V172 media observer partial")
        return s
    for marker in ("SCARLET_V172_RESTORE_PORTRAIT","SCARLET_V171_LANDSCAPE_SCENE_FRAME"):
        if marker not in s:raise ValueError("V172 media prerequisite missing "+marker)
    if s.count(OLD)!=1 or s.count(HOOK)!=1:raise ValueError("V172 media pinned source mismatch")
    if "\n- (void)dealloc {" in s:raise ValueError("Existing dealloc must be reconciled before instrumenting")
    return s.replace(OLD,NEW,1).replace(HOOK,METHOD+HOOK,1)

def main(root):
    p=root/FILE
    if not p.is_file() or p.is_symlink():raise ValueError("pinned source missing")
    before=p.read_text(encoding="utf-8");after=patch(before)
    if patch(after)!=after:raise ValueError("not idempotent")
    if after!=before:p.write_text(after,encoding="utf-8")
    print("[PASS] V172 media failure notifications recorded without payloads")

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("usage: patch_v172_media_evidence.py <LiveContainer>")
    main(Path(sys.argv[1]))
