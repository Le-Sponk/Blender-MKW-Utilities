"""Wiimms SZS / ABMatt integration tests.

blender -b --factory-startup --python wszst_test.py -- <addon_src>
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

tag = bpy.app.version_string.split()[0]
OUT = _outdir("wszst_" + tag)

R = {}
R["wszst_detected"] = mod._detect_wszst()
R["abmatt_detected"] = mod._detect_abmatt()
R["kcl_script_present"] = os.path.isfile(os.path.join(t, "lower-walls.txt"))
R["kcl_menu_registered"] = mod.export_kcl_button in bpy.types.TOPBAR_MT_file_export._dyn_ui_initialize()


def scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
    bpy.context.active_object.name = "road_F0000"
    bpy.ops.mesh.primitive_cube_add(size=4, location=(0, 8, 2))
    bpy.context.active_object.name = "wall_F000C"


# ---- KCL export, default quality ----
scene()
bpy.ops.object.select_all(action='SELECT')
kcl = os.path.join(OUT, "course.kcl")
try:
    bpy.ops.kcl.export('EXEC_DEFAULT', filepath=kcl,
                       kclExportFlagOnly=True, kclExportUnBeanCorner="LOWER")
    R["kcl_export_lower"] = os.path.isfile(kcl) and os.path.getsize(kcl) > 0
except Exception:
    traceback.print_exc(); R["kcl_export_lower"] = False

# independent validation with the real tool
if R.get("kcl_export_lower"):
    p = subprocess.run(["wkclt", "analyze", kcl], capture_output=True, text=True)
    R["wkclt_analyze_rc"] = p.returncode
    p2 = subprocess.run(["wszst", "filetype", kcl], capture_output=True, text=True)
    R["wszst_filetype"] = "KCL" in p2.stdout

# ---- KCL export with each quality preset ----
for q in ("SMALL", "MEDIUM", "CHARY"):
    scene(); bpy.ops.object.select_all(action='SELECT')
    f = os.path.join(OUT, f"q_{q}.kcl")
    try:
        bpy.ops.kcl.export('EXEC_DEFAULT', filepath=f, kclExportFlagOnly=True,
                           kclExportQuality=q, kclExportUnBeanCorner="NONE")
        R[f"kcl_{q}"] = os.path.isfile(f) and os.path.getsize(f) > 0
    except Exception:
        traceback.print_exc(); R[f"kcl_{q}"] = False

# ---- KCL import round-trip ----
if R.get("kcl_export_lower"):
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete()
    try:
        bpy.ops.kcl.load('EXEC_DEFAULT', filepath=kcl)
        meshes = [o for o in bpy.data.objects if o.type == 'MESH']
        R["kcl_import"] = len(meshes) > 0
        R["kcl_import_tris"] = sum(len(o.data.polygons) for o in meshes)
    except Exception:
        traceback.print_exc(); R["kcl_import"] = False

# ---- Minimap BRRES via ABMatt ----
if R["abmatt_detected"]:
    # 1. guard must fire when a mesh has no material
    scene()
    o = bpy.data.objects["road_F0000"]
    m0 = bpy.data.materials.new("mapmat"); m0.use_nodes = True
    o.data.materials.append(m0)
    guard_hit = False
    try:
        bpy.ops.export.minimap('EXEC_DEFAULT', filepath=os.path.join(OUT, "bad.brres"))
    except RuntimeError as e:
        guard_hit = "every exported mesh to have a material" in str(e)
    R["no_material_guard"] = guard_hit

    # 2. valid case: every mesh has a material
    scene()
    for i, nm in enumerate(("road_F0000", "wall_F000C")):
        ob = bpy.data.objects[nm]
        mm = bpy.data.materials.new("mat%d" % i); mm.use_nodes = True
        ob.data.materials.append(mm)
    brres = os.path.join(OUT, "course_map.brres")
    try:
        R["minimap_poll"] = bpy.ops.export.minimap.poll()
        bpy.ops.export.minimap('EXEC_DEFAULT', filepath=brres)
        R["minimap_export"] = os.path.isfile(brres) and os.path.getsize(brres) > 0
        if R["minimap_export"]:
            p = subprocess.run(["wszst", "filetype", brres], capture_output=True, text=True)
            R["minimap_is_brres"] = "BRRES" in p.stdout
            # no stray intermediates left behind
            R["no_temp_leftovers"] = not any(
                f.endswith((".obj", ".mtl", ".dae")) for f in os.listdir(OUT))
    except Exception:
        traceback.print_exc(); R["minimap_export"] = False

print("=== RESULTS ===")
for k, v in R.items():
    print(f"  {k} = {v}")
bad = [k for k, v in R.items() if v is False]
print("VERDICT:", "PASS" if not bad else "FAIL " + ",".join(bad))
