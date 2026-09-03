#!/usr/bin/env python3
"""Build the installable ZIP for MKW Utilities.

Produces a single archive that works both ways:

  * Blender 4.2+ - Extensions system (drag-and-drop / Install from Disk).
                    Uses blender_manifest.toml.
  * Blender 3.1 - 4.1 - Legacy add-on (Preferences > Add-ons > Install).
                    Uses bl_info.

Both metadata blocks are present; each Blender version reads the one it
understands and ignores the other.
"""
import os
import re
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
PKG = "MKW-Utilities"

FILES = [
    "__init__.py",
    "export_obj.py",
    "export_dae.py",
    "blender_manifest.toml",
    "lower-walls.txt",
    "diagnose.py",
    "README.md",
    "LICENSE",
    "NOTICE.md",
]


def get_version():
    src = open(os.path.join(ROOT, "__init__.py"), encoding="utf-8").read()
    m = re.search(r'"version"\s*:\s*\((\d+),\s*(\d+),\s*(\d+)\)', src)
    return ".".join(m.groups())


def check_version_sync(ver):
    """The manifest and bl_info must agree, or the two install paths differ."""
    man = open(os.path.join(ROOT, "blender_manifest.toml"), encoding="utf-8").read()
    m = re.search(r'^version\s*=\s*"([^"]+)"', man, re.M)
    if not m:
        raise SystemExit("blender_manifest.toml has no version field")
    if m.group(1) != ver:
        raise SystemExit(
            "version mismatch: bl_info says %s, blender_manifest.toml says %s"
            % (ver, m.group(1)))


def build():
    ver = get_version()
    check_version_sync(ver)
    os.makedirs(DIST, exist_ok=True)

    out = os.path.join(DIST, "%s-%s.zip" % (PKG, ver))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in FILES:
            path = os.path.join(ROOT, f)
            if not os.path.isfile(path):
                raise SystemExit("missing file: " + f)
            z.write(path, "%s/%s" % (PKG, f))
    print("built", out)
    return out


if __name__ == "__main__":
    build()
