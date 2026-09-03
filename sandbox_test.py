"""Sandbox (Flatpak/Snap) tool-discovery tests.

blender -b --factory-startup --python sandbox_test.py -- <addon_src> <mode>

modes:
  hostpath - tools only reachable via /run/host/... (Flatpak filesystem=host)
  snapfs   - tools only reachable via /var/lib/snapd/hostfs/...
  detect   - sandbox markers present, tools genuinely absent
"""
import bpy, addon_utils, shutil, os, sys, traceback

import tempfile

def _outdir(name):
    """Scratch directory for test artifacts."""
    d = os.path.join(tempfile.gettempdir(), "mkwu_" + name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    return d

argv = sys.argv
rest = argv[argv.index("--") + 1:]
src, mode = rest[0], rest[1]
name = os.path.basename(src.rstrip("/"))

# Hide the real install from PATH and from the plain search dirs.
os.environ["PATH"] = "/usr/bin:/bin"

d = bpy.utils.user_resource('SCRIPTS', path="addons", create=True)
t = os.path.join(d, name)
shutil.rmtree(t, ignore_errors=True)
shutil.copytree(src, t)
addon_utils.modules_refresh()
addon_utils.enable(name, default_set=True)
mod = sys.modules[name]

R = {}
print("BLENDER", bpy.app.version_string, "MODE", mode)

if mode == "detect":
    # Pretend we are inside a Flatpak with no host access at all.
    os.environ["FLATPAK_ID"] = "org.blender.Blender"
    # Simulate genuine sandbox isolation: none of the search dirs contain
    # the tools (Flatpak without --filesystem=host).
    mod._TOOL_SEARCH_DIRS[:] = ["/nonexistent/a", "/nonexistent/b"]
    mod._tool_cache.clear()
    R["sandbox_detected"] = mod.detect_sandbox()
    R["reports_missing"] = (mod.refresh_tool_detection() is False)
    R["no_false_positive"] = not mod.wszstInstalled
else:
    real_prefix = ("/run/host" if mode == "hostpath"
                   else "/var/lib/snapd/hostfs")
    # The genuine sandbox paths are listed in the addon...
    R["search_dir_listed"] = any(p.startswith(real_prefix)
                                 for p in mod._TOOL_SEARCH_DIRS)
    # The real sandbox mounts may be noexec (or absent) on the test machine,
    # so exercise the identical code path against an exec-capable stand-in.
    # Set MKWU_FAKE_HOST / MKWU_FAKE_SNAP to a directory containing
    # usr/local/bin/wszst to run this test.
    envvar = "MKWU_FAKE_HOST" if mode == "hostpath" else "MKWU_FAKE_SNAP"
    prefix = os.environ.get(envvar)
    if not prefix:
        print("SKIP: set %s to a directory containing usr/local/bin/wszst" % envvar)
        raise SystemExit(0)
    mod._TOOL_SEARCH_DIRS.insert(0, os.path.join(prefix, "usr", "local", "bin"))
    R["resolves_from_hostfs"] = mod._resolve_tool("wszst", use_cache=False).startswith(prefix)
    R["detects"] = mod.refresh_tool_detection()
    R["resolved"] = mod._resolve_tool("wszst")

    # A real export must work using that host path.
    OUT = _outdir("sandbox_" + mode)
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.mesh.primitive_plane_add(size=20)
    bpy.context.active_object.name = "road_F0000"
    bpy.ops.object.select_all(action='SELECT')
    kcl = os.path.join(OUT, "c.kcl")
    try:
        bpy.ops.kcl.export('EXEC_DEFAULT', filepath=kcl,
                           kclExportFlagOnly=True, kclExportUnBeanCorner="LOWER")
        R["kcl_export"] = os.path.isfile(kcl) and os.path.getsize(kcl) > 0
    except Exception:
        traceback.print_exc()
        R["kcl_export"] = False

print("=== RESULTS ===")
for k, v in R.items():
    print(f"  {k} = {v}")
bad = [k for k, v in R.items() if v is False or v == ""]
print("VERDICT:", "PASS" if not bad else "FAIL " + ",".join(bad))
