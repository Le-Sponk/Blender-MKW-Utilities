"""KCL export geometry and import of duplicate flag names.

blender -b --factory-startup --python roundtrip_test.py -- <addon_src>
"""
import bpy, addon_utils, shutil, os, sys, traceback, math, subprocess

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

OUT = _outdir("roundtrip")
R = {}
print("BLENDER", bpy.app.version_string)


def build_loop_course():
    """A ring road (flag 0x00) with a wall ring (flag 0x0C) - 2 unique flags."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Road: a flat torus-ish ring made of segments -> several separate objects
    # so the importer will produce duplicate-name objects.
    for i in range(4):
        a = i * math.pi / 2
        bpy.ops.mesh.primitive_plane_add(size=40,
                                         location=(math.cos(a) * 60, math.sin(a) * 60, 0))
        o = bpy.context.active_object
        o.name = "ROAD_00_F0000" if i == 0 else "ROAD_00_F0000.%03d" % i

    for i in range(4):
        a = i * math.pi / 2 + math.pi / 4
        bpy.ops.mesh.primitive_cube_add(size=20,
                                        location=(math.cos(a) * 90, math.sin(a) * 90, 10))
        o = bpy.context.active_object
        o.name = "WALL_0C_F000C" if i == 0 else "WALL_0C_F000C.%03d" % i

    return [o.name for o in bpy.context.scene.objects]


names = build_loop_course()
print("SCENE OBJECTS", names)
R["built_objects"] = len(names)

# total geometry before export
def total_tris():
    n = 0
    for o in bpy.context.scene.objects:
        if o.type == 'MESH':
            me = o.data
            n += sum(len(p.vertices) - 2 for p in me.polygons)
    return n

R["source_tris"] = total_tris()

# ---- Export ----
bpy.ops.object.select_all(action='SELECT')
kcl = os.path.join(OUT, "course.kcl")
try:
    bpy.ops.kcl.export('EXEC_DEFAULT', filepath=kcl,
                       kclExportFlagOnly=True, kclExportUnBeanCorner="LOWER")
    R["export_ok"] = os.path.isfile(kcl) and os.path.getsize(kcl) > 0
    R["kcl_bytes"] = os.path.getsize(kcl) if os.path.isfile(kcl) else 0
except Exception:
    traceback.print_exc(); R["export_ok"] = False

# ---- Inspect the KCL with the real tool: how many triangles / what bounds? ----
if R.get("export_ok"):
    p = subprocess.run(["wkclt", "analyze", kcl], capture_output=True, text=True)
    print("---- wkclt analyze ----")
    print(p.stdout)
    # dump gives per-flag detail
    p2 = subprocess.run(["wkclt", "flags", kcl], capture_output=True, text=True)
    print("---- wkclt flags ----")
    print(p2.stdout[:2000])
    print(p2.stderr[:500])

# ---- Import back (this is where the KeyError happens) ----
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete()
try:
    bpy.ops.kcl.load('EXEC_DEFAULT', filepath=kcl)
    R["import_ok"] = True
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    R["imported_objects"] = len(meshes)
    R["imported_names"] = sorted(o.name for o in meshes)
    R["imported_tris"] = total_tris()
except Exception as e:
    traceback.print_exc()
    R["import_ok"] = False
    R["import_error"] = "%s: %s" % (type(e).__name__, e)

print("=== RESULTS ===")
for k, v in R.items():
    print(f"  {k} = {v}")
