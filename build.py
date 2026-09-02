#!/usr/bin/env python3
"""Build installable ZIPs for MKW Utilities.

Produces:
  dist/MKW-Utilities-<ver>-legacy.zip      -> Blender 3.1 - 4.1 (Edit > Preferences > Add-ons > Install)
  dist/MKW-Utilities-<ver>-extension.zip   -> Blender 4.2+     (Extensions / drag-and-drop)

The legacy ZIP contains a top-level folder (Blender requires this).
The extension ZIP is flat with blender_manifest.toml at the root.
"""
import os
import re
import shutil
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
PKG = "MKW-Utilities"
FILES = ["__init__.py", "export_obj.py", "README.md", "lower-walls.txt",
         "diagnose.py", "LICENSE", "NOTICE.md"]


def get_version():
    src = open(os.path.join(ROOT, "__init__.py"), encoding="utf-8").read()
    m = re.search(r'"version"\s*:\s*\((\d+),\s*(\d+),\s*(\d+)\)', src)
    return ".".join(m.groups())


def build():
    ver = get_version()
    os.makedirs(DIST, exist_ok=True)

    legacy = os.path.join(DIST, f"{PKG}-{ver}-legacy.zip")
    with zipfile.ZipFile(legacy, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            z.write(os.path.join(ROOT, f), f"{PKG}/{f}")
    print("built", legacy)

    ext = os.path.join(DIST, f"{PKG}-{ver}-extension.zip")
    with zipfile.ZipFile(ext, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES + ["blender_manifest.toml"]:
            z.write(os.path.join(ROOT, f), f)
    print("built", ext)
    return legacy, ext


if __name__ == "__main__":
    build()
