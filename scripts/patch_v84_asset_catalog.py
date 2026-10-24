#!/usr/bin/env python3
"""V84: preserve icon assets while preventing Xcode 27.2 duplicate raw copies.

Patch only the pinned SideStore Xcode project's filesystem-synchronized target.
Do NOT remove/rename .png, Contents.json, imagesets or appiconsets, and do not
touch app data, signing identity, App IDs, or the main bundle identifier.
"""
from pathlib import Path
import sys

PROJECT = Path("AltStore.xcodeproj/project.pbxproj")
CATALOG = Path("AltStore/Resources/Icons.xcassets")
MARK = "SCARLET_V84_XCODE272_ASSET_CATALOG"
BUILD_ID = "C8427A0031010D0000000001"
FILE_ID = "C8427A0031010D0000000002"
TARGET_ID = "BFD247692284B9A500981D42"


def one(source: str, old: str, new: str, what: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"V84 {what}: expected exactly one pinned anchor, found {source.count(old)}")
    return source.replace(old, new, 1)


def patch(source: str) -> str:
    if MARK in source:
        required = [
            f"{BUILD_ID} /* Icons.xcassets in Resources */",
            f"{FILE_ID} /* Icons.xcassets */",
            "Resources/Icons.xcassets,",
            "lastKnownFileType = folder.assetcatalog",
        ]
        if source.count(MARK) != 1 or any(token not in source for token in required):
            raise ValueError("V84 partial or corrupt asset catalog patch")
        return source
    if any(x in source for x in (BUILD_ID, FILE_ID)):
        raise ValueError("V84 GUID conflict with pinned project")
    if f"target = {TARGET_ID} /* SideStore */;" not in source:
        raise ValueError("V84 pinned SideStore target is absent")
    source = one(source, "/* Begin PBXBuildFile section */",
        "/* Begin PBXBuildFile section */\n"
        f"\t\t{BUILD_ID} /* Icons.xcassets in Resources */ = "
        f"{{isa = PBXBuildFile; fileRef = {FILE_ID} /* Icons.xcassets */; }}; "
        f"/* {MARK} */", "build file")
    source = one(source, "/* Begin PBXFileReference section */",
        "/* Begin PBXFileReference section */\n"
        f"\t\t{FILE_ID} /* Icons.xcassets */ = "
        "{isa = PBXFileReference; lastKnownFileType = folder.assetcatalog; "
        "path = AltStore/Resources/Icons.xcassets; sourceTree = \"<group>\"; };",
        "asset file reference")
    source = one(source,
        "\t\t\tchildren = (\n\t\t\t\tA8EEC8412F4B146A00F2436D /* AltStore */,",
        "\t\t\tchildren = (\n"
        f"\t\t\t\t{FILE_ID} /* Icons.xcassets */,\n"
        "\t\t\t\tA8EEC8412F4B146A00F2436D /* AltStore */,", "root group")
    # The SideStore target's AltStore synced folder currently copies each image
    # and Contents.json verbatim. Exclude the *whole* catalog from automatic
    # membership; the explicit PBXBuildFile compiles it once with actool.
    side_tag = "A8EEC8CB2F4B146B00F2436D /* PBXFileSystemSynchronizedBuildFileExceptionSet */ = {"
    start = source.index(side_tag)
    end = source.index("\n\t\t};", start) + len("\n\t\t};")
    subset = source[start:end]
    if f"target = {TARGET_ID} /* SideStore */;" not in subset:
        raise ValueError("V84 wrong synchronized exception target")
    updated = one(subset, "\t\t\tmembershipExceptions = (\n\t\t\t\tInfo.plist,",
        "\t\t\tmembershipExceptions = (\n\t\t\t\tInfo.plist,\n"
        "\t\t\t\tResources/Icons.xcassets,", "synchronized exclusion")
    source = source[:start] + updated + source[end:]
    resource_tag = "BFD247682284B9A500981D42 /* Resources */ = {"
    start = source.index(resource_tag)
    end = source.index("\n\t\t};", start) + len("\n\t\t};")
    subset = source[start:end]
    updated = one(subset,
        "\t\t\tfiles = (\n\t\t\t\tA84596F62F7DC4C90000B8CD /* SideStore.conf in Resources */,",
        "\t\t\tfiles = (\n"
        f"\t\t\t\t{BUILD_ID} /* Icons.xcassets in Resources */,\n"
        "\t\t\t\tA84596F62F7DC4C90000B8CD /* SideStore.conf in Resources */,",
        "SideStore resources")
    source = source[:start] + updated + source[end:]
    if patch(source) != source:
        raise ValueError("V84 second pass must be idempotent")
    return source


def apply(root: Path) -> None:
    catalog = root / CATALOG
    if not catalog.is_dir() or not (catalog / "Contents.json").is_file():
        raise ValueError("V84 original icon catalog missing; refusing to change project")
    project = root / PROJECT
    original = project.read_text(encoding="utf8")
    modified = patch(original)
    if original != modified:
        project.write_text(modified, encoding="utf8")
    print("[PASS] V84: one compiled asset catalog; raw synchronized icon copies excluded; icons preserved")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch_v84_asset_catalog.py <pinned EmbeddedSideStore source>")
    apply(Path(sys.argv[1]))
