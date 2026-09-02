"""Regression test for the 'WSZST not detected' bug.

Simulates Blender launched from a desktop icon (no /usr/local/bin on PATH).

blender -b --factory-startup --python detect_test.py -- <addon_src>
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
src = argv[argv.index("--") + 1]
name = os.path.basename(src.rstrip("/"))

# CRITICAL: strip the tool dir from PATH *before* the addon registers,
# reproducing a GUI launch.
os.environ["PATH"] = "/usr/bin:/bin"

d = bpy.utils.user_resource('SCRIPTS', path="addons", create=True)
t = os.path.join(d, name)
shutil.rmtree(t, ignore_errors=True)
shutil.copytree(src, t)
addon_utils.modules_refresh()
addon_utils.enable(name, default_set=True)
mod = sys.modules[name]

R = {}
print("BLENDER", bpy.app.version_string)
print("PATH", os.environ["PATH"])
print("shutil.which(wszst) =", shutil.which("wszst"))

# 1. Detection must succeed despite wszst being absent from PATH
R["resolved_wszst"] = mod._resolve_tool("wszst")
R["detected_without_path"] = mod.wszstInstalled
R["kcl_export_menu"] = mod.export_kcl_button in bpy.types.TOPBAR_MT_file_export._dyn_ui_initialize()
R["kcl_import_menu"] = mod.import_kcl_button in bpy.types.TOPBAR_MT_file_import._dyn_ui_initialize()

# 2. A real KCL export must work with the reduced PATH
OUT = _outdir("detect")
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
bpy.ops.mesh.primitive_plane_add(size=20)
bpy.context.active_object.name = "road_F0000"
bpy.ops.mesh.primitive_cube_add(size=4, location=(0, 8, 2))
bpy.context.active_object.name = "wall_F000C"
bpy.ops.object.select_all(action='SELECT')
kcl = os.path.join(OUT, "c.kcl")
try:
    bpy.ops.kcl.export('EXEC_DEFAULT', filepath=kcl,
                       kclExportFlagOnly=True, kclExportUnBeanCorner="LOWER")
    R["kcl_export_no_path"] = os.path.isfile(kcl) and os.path.getsize(kcl) > 0
except Exception:
    traceback.print_exc()
    R["kcl_export_no_path"] = False

# 3. Import round-trip too (uses wkclt decode)
if R.get("kcl_export_no_path"):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    try:
        bpy.ops.kcl.load('EXEC_DEFAULT', filepath=kcl)
        R["kcl_import_no_path"] = len([o for o in bpy.data.objects if o.type == 'MESH']) > 0
    except Exception:
        traceback.print_exc()
        R["kcl_import_no_path"] = False

# 4. The manual re-check operator must work
R["refresh_operator"] = bpy.ops.mkw.refresh_tools() == {'FINISHED'}

# 5. Explicit preference override should also resolve the tools
prefs = bpy.context.preferences.addons[name].preferences
prefs.wszst_path = "/usr/local/bin"
mod._tool_cache.clear()
R["pref_override"] = bool(mod._resolve_tool("wszst"))

# 6. A bogus preference must not crash; falls back to search
prefs.wszst_path = "/nonexistent/path/xyz"
mod._tool_cache.clear()
R["bogus_pref_safe"] = bool(mod._resolve_tool("wszst"))

print("=== RESULTS ===")
for k, v in R.items():
    print(f"  {k} = {v}")
bad = [k for k, v in R.items() if v is False or v == ""]
print("VERDICT:", "PASS" if not bad else "FAIL " + ",".join(bad))
