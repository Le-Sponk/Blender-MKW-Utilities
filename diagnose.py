"""MKW Utilities -  environment diagnostic.

Run this INSIDE Blender (Scripting tab > New > paste > Run Script), then
copy the console output. It reports how Blender is packaged and what it can
see, which explains 'WSZST not found' problems.
"""
import os
import shutil
import subprocess
import sys

import bpy

print("=" * 60)
print("MKW UTILITIES DIAGNOSTIC")
print("=" * 60)

print("Blender     :", bpy.app.version_string)
print("Executable  :", bpy.app.binary_path)
print("Platform    :", sys.platform)

# --- How is Blender packaged? ---
flatpak = os.path.exists("/.flatpak-info") or bool(os.environ.get("FLATPAK_ID"))
snap = bool(os.environ.get("SNAP") or os.environ.get("SNAP_NAME"))
print("\n--- Packaging ---")
print("Flatpak     :", flatpak, os.environ.get("FLATPAK_ID", ""))
print("Snap        :", snap, os.environ.get("SNAP_NAME", ""))
if flatpak:
    print(">> Flatpak Blender CANNOT see the host's /usr/local by default.")
    print(">> Fix: flatpak override --user --filesystem=host org.blender.Blender")
if snap:
    print(">> Snap Blender is confined and cannot run host binaries.")
    print(">> Fix: install Blender from blender.org or via apt instead.")

print("\n--- PATH as seen by Blender ---")
for p in os.environ.get("PATH", "").split(os.pathsep):
    print("   ", p)

print("\n--- Filesystem visibility ---")
for p in ("/usr", "/usr/local", "/usr/local/bin",
          "/run/host/usr/local/bin", "/var/lib/snapd/hostfs/usr/local/bin"):
    print(f"   {p:45} exists={os.path.isdir(p)}")

print("\n--- Tool lookup ---")
for tool in ("wszst", "wkclt", "abmatt"):
    w = shutil.which(tool)
    print(f"   shutil.which({tool:6}) = {w}")

CANDIDATES = [
    "/usr/local/bin", "/usr/bin", "/bin", "/opt/homebrew/bin",
    os.path.expanduser("~/.local/bin"),
    "/run/host/usr/local/bin", "/var/lib/snapd/hostfs/usr/local/bin",
    r"C:\Program Files\Wiimm\SZS\bin",
]
print("\n--- Direct file checks ---")
found_any = False
for d in CANDIDATES:
    for exe in ("wszst", "wszst.exe"):
        f = os.path.join(d, exe)
        if os.path.isfile(f):
            found_any = True
            print(f"   FOUND {f}  executable={os.access(f, os.X_OK)}")
            try:
                out = subprocess.run([f, "version"], capture_output=True,
                                     text=True, timeout=5).stdout.strip()
                print(f"         runs -> {out[:70]}")
            except Exception as e:
                print(f"         CANNOT RUN: {type(e).__name__}: {e}")
if not found_any:
    print("   wszst not found in any known location.")

print("\n--- flatpak-spawn (host escape) ---")
try:
    p = subprocess.run(["flatpak-spawn", "--host", "wszst", "version"],
                       capture_output=True, text=True, timeout=10)
    print("   stdout:", p.stdout.strip()[:70] or "(empty)")
    print("   works :", p.stdout.startswith("wszst: Wiimms SZS Tool"))
except Exception as e:
    print("   unavailable:", type(e).__name__, e)

print("\n--- Add-on's own view ---")
mod = None
for name, m in sys.modules.items():
    if name.endswith("mkw_utilities") or name == "Blender-MKW-Utilities":
        mod = m
        break
if mod is None:
    print("   Add-on not currently enabled.")
else:
    print("   module          :", mod.__name__)
    print("   wszstInstalled  :", getattr(mod, "wszstInstalled", "?"))
    if hasattr(mod, "_resolve_tool"):
        print("   resolved wszst  :", repr(mod._resolve_tool("wszst", use_cache=False)))
        print("   resolved wkclt  :", repr(mod._resolve_tool("wkclt", use_cache=False)))
    if hasattr(mod, "detect_sandbox"):
        print("   sandbox         :", repr(mod.detect_sandbox()))

print("=" * 60)
print("Copy everything above and send it back.")
print("=" * 60)
