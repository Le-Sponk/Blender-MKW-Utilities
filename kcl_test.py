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
bpy.ops.object.camera_add()
bpy.context.active_object.name = "export_helper_camera"
bpy.ops.object.select_all(action='SELECT')

# What does the plugin consider a flagged object?
names = ["road_F0000", "wall_F000C"]
R["flag_parse"] = {n: bool(mod.checkFlagInName001(n, full=False)) for n in names}
print("FLAG_PARSE", R["flag_parse"])

# ---- KCL export (default settings => uses lower-walls.txt) ----
kcl_path = os.path.join(OUT, "course.kcl")
bpy.ops.object.select_all(action='SELECT')
try:
    options = mod.KclExportOptions(
        filepath=kcl_path,
        kclExportFlagOnly=True,
        kclExportSelection=False,
        kclExportUnBeanCorner="LOWER",
    )
    reports = []
    result = mod.export_kcl(
        bpy.context, options, lambda level, message: reports.append((level, message)))
    print("KCL_EXPORT_RESULT", result)
    R["kcl_result_dict"] = (
        result["ok"] is True
        and result["objects"] == 2
        and result["triangles"] > 0
        and result["skipped_objects"] == []
        and len(result["extent"]) == 3
    )
    R["kcl_export"] = os.path.isfile(kcl_path) and os.path.getsize(kcl_path) > 0
    selection_path = os.path.join(OUT, "selection.kcl")
    selection_result = mod.export_kcl(
        bpy.context,
        mod.KclExportOptions(
            filepath=selection_path,
            kclExportSelection=True,
            kclExportUnBeanCorner="NONE",
        ),
        lambda _level, _message: None,
    )
    R["kcl_selection_ignores_non_mesh"] = (
        selection_result["ok"] is True and selection_result["objects"] == 2
    )
    wrapper_path = os.path.join(OUT, "operator.kcl")
    wrapper_status = bpy.ops.kcl.export(
        'EXEC_DEFAULT', filepath=wrapper_path,
        kclExportFlagOnly=True, kclExportSelection=False,
        kclExportUnBeanCorner="NONE")
    R["kcl_operator_wrapper"] = (
        wrapper_status == {'FINISHED'} and os.path.isfile(wrapper_path)
    )
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

# ---- Minimap export API ----
for obj in [o for o in bpy.data.objects if o.type == 'MESH']:
    if not obj.data.materials:
        obj.data.materials.append(bpy.data.materials.new(obj.name + "_material"))
minimap_path = os.path.join(OUT, "map.brres")
try:
    reports = []
    result = mod.export_minimap_brres(
        bpy.context,
        mod.MinimapExportOptions(filepath=minimap_path),
        lambda level, message: reports.append((level, message)),
    )
    print("MINIMAP_EXPORT_RESULT", result)
    R["minimap_result_dict"] = (
        result["ok"] is True
        and result["objects"] == 2
        and result["triangles"] > 0
        and result["skipped_objects"] == []
    )
    R["minimap_export"] = (
        os.path.isfile(minimap_path) and os.path.getsize(minimap_path) > 0
    )
    wrapper_path = os.path.join(OUT, "operator_map.brres")
    wrapper_status = bpy.ops.export.minimap(
        'EXEC_DEFAULT', filepath=wrapper_path)
    R["minimap_operator_wrapper"] = (
        wrapper_status == {'FINISHED'} and os.path.isfile(wrapper_path)
    )
except Exception:
    traceback.print_exc()
    R["minimap_result_dict"] = False
    R["minimap_export"] = False

# Failure results stay machine-readable and never publish stale output.
common = {"ok", "filepath", "objects", "triangles", "skipped_objects", "error"}
original_detect = mod._detect_abmatt
try:
    mod._detect_abmatt = lambda: False
    result = mod.export_minimap_brres(
        bpy.context,
        mod.MinimapExportOptions(filepath=os.path.join(OUT, "missing.brres")),
        lambda _level, _message: None,
    )
    R["minimap_missing_tool_result"] = (
        result["ok"] is False and common <= set(result) and bool(result["error"])
    )
finally:
    mod._detect_abmatt = original_detect

stale_path = os.path.join(OUT, "stale_map.brres")
with open(stale_path, "wb") as stream:
    stream.write(b"preserve me")
original_run = mod.subprocess.run
original_detect = mod._detect_abmatt
calls = []
try:
    mod._detect_abmatt = lambda: True
    def fail_process(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(
            args, 1, stdout="", stderr="forced failure")
    mod.subprocess.run = fail_process
    result = mod.export_minimap_brres(
        bpy.context,
        mod.MinimapExportOptions(filepath=stale_path),
        lambda _level, _message: None,
    )
    with open(stale_path, "rb") as stream:
        preserved = stream.read() == b"preserve me"
    R["minimap_failure_preserves_output"] = (
        result["ok"] is False
        and preserved
        and bool(calls)
        and "forced failure" in result["error"]
    )
finally:
    mod.subprocess.run = original_run
    mod._detect_abmatt = original_detect

# Active-collection exports include meshes nested in child collections.
parent = bpy.data.collections.new("minimap_parent")
child = bpy.data.collections.new("minimap_child")
bpy.context.collection.children.link(parent)
parent.children.link(child)
mesh = bpy.data.meshes.new("nested_mesh")
mesh.from_pydata([(0, 0, 0), (1, 0, 0), (0, 1, 0)], [], [(0, 1, 2)])
nested = bpy.data.objects.new("nested_mesh", mesh)
child.objects.link(nested)
nested.data.materials.append(bpy.data.materials.new("nested_material"))
nested_path = os.path.join(OUT, "nested_map.brres")
result = mod.export_minimap_brres(
    bpy.context,
    mod.MinimapExportOptions(filepath=nested_path, exportCollection=True),
    lambda _level, _message: None,
)
R["minimap_nested_collection"] = (
    result["ok"] is True and result["objects"] == 3
)
bpy.data.objects.remove(nested, do_unlink=True)
bpy.data.collections.remove(child)
bpy.data.collections.remove(parent)

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
bad = [k for k, v in R.items() if v is False or v == ""]
print("VERDICT:", "PASS" if not bad else "FAIL " + ",".join(bad))
if bad:
    raise SystemExit(1)
