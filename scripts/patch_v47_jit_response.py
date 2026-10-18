#!/usr/bin/env python3
"""V47: reject false-positive JIT server responses. Does not grant JIT privileges."""
from pathlib import Path
import sys

def replace_once(path, old, new):
    p=Path(path)
    s=p.read_text()
    if new in s:
        print("Already patched:",p)
        return
    if s.count(old)!=1:
        raise SystemExit(f"Expected one JIT patch anchor in {p}, got {s.count(old)}")
    p.write_text(s.replace(old,new))
    print("Patched:",p)

root=Path(sys.argv[1]); side=Path(sys.argv[2])
replace_once(side/"SideStore/Core/Operations/StandaloneOperations/EnableJITOperation.swift",
    "    let (data, _) = try await URLSession.shared.data(from: fullURL)",
    """    var request = URLRequest(url: fullURL)
    request.timeoutInterval = 15
    let (data, response) = try await URLSession.shared.data(for: request)
    guard let http = response as? HTTPURLResponse else {
        throw SideJITServerErrorType.errorConnecting
    }
    guard (200...299).contains(http.statusCode) else {
        throw SideJITServerErrorType.other("SideJITServer HTTP \\(http.statusCode): " + String(decoding: data.prefix(512), as: UTF8.self))
    }""")
replace_once(root/"LiveContainerSwiftUI/Utilities/LCUtilsExtensions.swift",
    """                let request = URLRequest(url: launchJITUrl)
                let (data, _) = try await session.data(for: request)
                onServerMessage?(String(decoding: data, as: UTF8.self))""",
    """                var request = URLRequest(url: launchJITUrl)
                request.timeoutInterval = 15
                let (data, response) = try await session.data(for: request)
                guard let http = response as? HTTPURLResponse else {
                    onServerMessage?("SideJITServer returned a non-HTTP response; JIT is not verified.")
                    return false
                }
                guard (200...299).contains(http.statusCode) else {
                    onServerMessage?("SideJITServer HTTP \\(http.statusCode): " + String(decoding: data.prefix(512), as: UTF8.self))
                    return false
                }
                let result = String(decoding: data, as: UTF8.self)
                onServerMessage?(result)
                guard result.contains("Enabled JIT for") else {
                    onServerMessage?("SideJITServer did not confirm JIT activation.")
                    return false
                }
                onServerMessage?("Server confirmed JIT request; runtime verification is still required.")""")
