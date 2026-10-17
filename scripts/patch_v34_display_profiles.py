#!/usr/bin/env python3
"""V34: persistent per-bundle guest display controls without modifying guest IPAs."""
from pathlib import Path
import sys

TARGET = Path("MultitaskSupport/MultitaskAppWindow.swift")
MARKER = "NRG_V34_GUEST_DISPLAY_PROFILE_V1"

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"V34 anchor mismatch ({text.count(old)}): {old[:90]}")
    return text.replace(old, new, 1)

def patch(text):
    if MARKER in text:
        if text.count(MARKER) != 1 or "v34DisplayScale" not in text:
            raise ValueError("partial V34 display patch")
        return text
    text = replace_once(text,
        '    @State private var didRequestManualClose = false\n',
        '''    @State private var didRequestManualClose = false
    // NRG_V34_GUEST_DISPLAY_PROFILE_V1: bundle-scoped, persisted in LC app group.
    @State private var v34DisplayScale: Double = 1.0
    @State private var v34ControlsExpanded = false
    private var v34ProfileKey: String {
        "NRG.V34.DisplayScale." + (appInfo?.bundleId ?? "unknown")
    }
    private func v34LoadDisplayProfile() {
        let saved = LCUtils.appGroupUserDefault.object(forKey: v34ProfileKey) as? Double ?? 1.0
        v34DisplayScale = min(1.0, max(0.70, saved))
    }
    private func v34SaveDisplayProfile(_ scale: Double) {
        LCUtils.appGroupUserDefault.set(min(1.0, max(0.70, scale)), forKey: v34ProfileKey)
    }
''')
    text = replace_once(text,
        '''                .background(.black)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .ignoresSafeArea(.all, edges: .all)
            .navigationTitle(Text("\\(appInfo.displayName) - \\(String(pid))"))''',
        '''                .background(.black)
                .scaleEffect(v34DisplayScale, anchor: .center)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            // Preserve native status-bar and home-indicator safe areas.
            // A bounded <=1 scale prevents clipping the guest's top controls.
            .overlay(alignment: .topTrailing) {
                HStack(spacing: 8) {
                    if v34ControlsExpanded {
                        Button {
                            let next = max(0.70, v34DisplayScale - 0.05)
                            v34DisplayScale = next
                            v34SaveDisplayProfile(next)
                        } label: {
                            Image(systemName: "minus.magnifyingglass")
                        }
                        Button {
                            v34DisplayScale = 1.0
                            v34SaveDisplayProfile(1.0)
                        } label: {
                            Image(systemName: "arrow.counterclockwise")
                        }
                        Button {
                            let next = min(1.0, v34DisplayScale + 0.05)
                            v34DisplayScale = next
                            v34SaveDisplayProfile(next)
                        } label: {
                            Image(systemName: "plus.magnifyingglass")
                        }
                        Text("\\(Int(v34DisplayScale * 100))%")
                            .font(.caption.monospacedDigit())
                    }
                    Button {
                        v34ControlsExpanded.toggle()
                    } label: {
                        Image(systemName: v34ControlsExpanded ? "xmark" : "slider.horizontal.3")
                    }
                }
                .buttonStyle(.plain)
                .padding(10)
                .background(.regularMaterial, in: Capsule())
                .padding(.top, 6)
                .padding(.trailing, 8)
                .accessibilityLabel("Guest display controls")
            }
            .toolbar(.hidden, for: .navigationBar)
            .onAppear { v34LoadDisplayProfile() }''')
    return text

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v34_display_profiles.py <LiveContainer-root>")
    target = Path(sys.argv[1]) / TARGET
    before = target.read_text()
    after = patch(before)
    if before != after:
        target.write_text(after)
        print("[PATCH] V34 safe-area overlay and persistent per-bundle scale")
    else:
        print("[PASS] V34 display patch already present")

if __name__ == "__main__":
    main()
