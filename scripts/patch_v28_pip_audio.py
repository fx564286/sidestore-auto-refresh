#!/usr/bin/env python3
"""V28: do not initialize a playback AVAudioSession merely to query PiP state.

Activate the host playback session only while a real PiP session starts/runs.
Do not manipulate an individual LiveProcess guest's AVAudioSession.
"""
from pathlib import Path
import sys

FILE = "MultitaskSupport/PiPManager.m"
MARKER = "NRG_V28_PIP_AUDIO_SESSION_LIFETIME"

def replace_one(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"V28 PiP audio {label}: anchor {n}")
    return s.replace(old, new, 1)

def patch(root: Path):
    path = root / FILE
    s = path.read_text(encoding="utf-8")
    if MARKER in s:
        if s.count(MARKER) != 1 or "AVAudioSessionSetActiveOptionNotifyOthersOnDeactivation" not in s:
            raise SystemExit("V28 PiP session partial patch")
        print("[PASS] V28 PiP audio session lifetime already patched")
        return
    old = """- (instancetype)init {
    NSError* error = nil;
    [[AVAudioSession sharedInstance] setCategory:AVAudioSessionCategoryPlayback error:&error];
    [[AVAudioSession sharedInstance] setActive:YES withOptions:1 error:&error];
    return self;
}
"""
    new = """// NRG_V28_PIP_AUDIO_SESSION_LIFETIME: simply querying PiP state must not
// keep the host in active playback mode while the user is on its home screen.
- (instancetype)init {
    return [super init];
}
"""
    s = replace_one(s, old, new, "eager initialization")
    old = """        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.3 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            [self.pipController startPictureInPicture];
        });
"""
    new = """        dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(0.3 * NSEC_PER_SEC)), dispatch_get_main_queue(), ^{
            NSError *audioError = nil;
            AVAudioSession *audioSession = [AVAudioSession sharedInstance];
            BOOL categoryReady = [audioSession setCategory:AVAudioSessionCategoryPlayback error:&audioError];
            BOOL audioReady = categoryReady && [audioSession setActive:YES error:&audioError];
            if (!audioReady) {
                NSLog(@"[NRG_V28_PIP_AUDIO] activation_failed");
                return;
            }
            [self.pipController startPictureInPicture];
        });
"""
    s = replace_one(s, old, new, "lazy activation")
    old = """    self.pipVideoCallContentView.transform = CGAffineTransformIdentity;
    if([NSUserDefaults.lcSharedDefaults boolForKey:@"LCAutoEndPiP"]) {
"""
    new = """    self.pipVideoCallContentView.transform = CGAffineTransformIdentity;
    NSError *audioError = nil;
    [[AVAudioSession sharedInstance] setActive:NO
                                  withOptions:AVAudioSessionSetActiveOptionNotifyOthersOnDeactivation
                                        error:&audioError];
    if (audioError) NSLog(@"[NRG_V28_PIP_AUDIO] deactivation_failed");
    if([NSUserDefaults.lcSharedDefaults boolForKey:@"LCAutoEndPiP"]) {
"""
    s = replace_one(s, old, new, "deactivation")
    old = """- (void)pictureInPictureController:(AVPictureInPictureController *)pictureInPictureController failedToStartPictureInPictureWithError:(NSError *)error {
    NSLog(@"%@", error.description);
}
"""
    new = """- (void)pictureInPictureController:(AVPictureInPictureController *)pictureInPictureController failedToStartPictureInPictureWithError:(NSError *)error {
    NSError *audioError = nil;
    [[AVAudioSession sharedInstance] setActive:NO withOptions:AVAudioSessionSetActiveOptionNotifyOthersOnDeactivation error:&audioError];
    NSLog(@"[NRG_V28_PIP_AUDIO] start_failed");
}
"""
    s = replace_one(s, old, new, "start failure cleanup")
    if s.count(MARKER) != 1:
        raise SystemExit("V28 PiP audio marker mismatch")
    path.write_text(s, encoding="utf-8")
    print("[PASS] V28 PiP audio activation is lazy; stop/failure releases host session")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v28_pip_audio.py <LiveContainer>")
    patch(Path(sys.argv[1]))
