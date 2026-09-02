"""KCL / minimap round-trip tests against the real Wiimms SZS Tools.

blender -b --factory-startup --python kcl_test.py -- <addon_src>
"""
import bpy, addon_utils, shutil, os, sys, traceback, subprocess

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
d = bpy.utils.user_resource('SCRIPTS', path="addons", create=True)
t = os.path.join(d, name)
shutil.rmtree(t, ignore_errors=True)
shutil.copytree(src, t)
addon_utils.modules_refresh()
addon_utils.enable(name, default_set=True)
mod = sys.modules[name]

OUT = _outdir("kcl")

R = {}
print("BLENDER", bpy.app.version_string)
print("WSZST_DETECTED", mod._detect_wszst())
R["wszst_detected"] = mod._detect_wszst()
R["kcl_script_present"] = os.path.isfile(os.path.join(t, "lower-walls.txt"))


def build_course():
    """A ground plane + a wall, named with KCL flags the plugin recognises."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    # road: flag 0x00
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    road = bpy.context.active_object
    road.name = "road_F0000"
    # wall: flag 0x0c (one of the wall types lower-walls.txt targets)
    bpy.ops.mesh.primitive_cube_add(size=4, location=(0, 8, 2))
    wall = bpy.context.active_object
    wall.name = "wall_F000C"
    return road, wall


build_course()

# What does the plugin consider a flagged object?
names = ["road_F0000", "wall_F000C"]
R["flag_parse"] = {n: bool(mod.checkFlagInName001(n, full=False)) for n in names}
print("FLAG_PARSE", R["flag_parse"])

# ---- KCL export (default settings => uses lower-walls.txt) ----
kcl_path = os.path.join(OUT, "course.kcl")
bpy.ops.object.select_all(action='SELECT')
try:
    res = bpy.ops.kcl.export(
        'EXEC_DEFAULT',
        filepath=kcl_path,
        kclExportFlagOnly=True,
        kclExportSelection=False,
        kclExportUnBeanCorner="LOWER",   # exercises the kcl-script path
    )
    print("KCL_EXPORT_RESULT", res)
    R["kcl_export"] = os.path.isfile(kcl_path) and os.path.getsize(kcl_path) > 0
except Exception:
    traceback.print_exc()
    R["kcl_export"] = False

if R.get("kcl_export"):
    print("KCL_SIZE", os.path.getsize(kcl_path))
    # Validate with the real tool
    p = subprocess.run(["wkclt", "analyze", kcl_path], capture_output=True, text=True)
    print("WKCLT_ANALYZE_RC", p.returncode)
    print(p.stdout[:1500])
    R["kcl_valid"] = p.returncode == 0

# ---- KCL import round-trip ----
if R.get("kcl_export"):
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    try:
        res = bpy.ops.kcl.load('EXEC_DEFAULT', filepath=kcl_path)
        meshes = [o for o in bpy.data.objects if o.type == 'MESH']
        print("KCL_IMPORT_RESULT", res, "objects:", len(meshes))
        R["kcl_import"] = len(meshes) > 0
        R["kcl_import_tris"] = sum(len(o.data.polygons) for o in meshes)
    except Exception:
        traceback.print_exc()
        R["kcl_import"] = False

print("=== RESULTS ===")
for k, v in R.items():
    print(f"  {k} = {v}")
