"""Full verification matrix for MKW Utilities across Blender versions.

blender -b --factory-startup --python verify.py -- <addon_src>
"""
import bpy, addon_utils, shutil, os, sys, traceback

argv = sys.argv
src = argv[argv.index("--") + 1]
name = os.path.basename(src.rstrip("/"))

d = bpy.utils.user_resource('SCRIPTS', path="addons", create=True)
t = os.path.join(d, name)
shutil.rmtree(t, ignore_errors=True)
shutil.copytree(src, t)
addon_utils.modules_refresh()

results = {}
def check(k, v):
    results[k] = v

print("BLENDER", bpy.app.version_string)

try:
    addon_utils.enable(name, default_set=True)
except Exception:
    traceback.print_exc()

check("enable", name in bpy.context.preferences.addons)

mod = sys.modules.get(name)
check("module_imported", mod is not None)

# Scene property group registered
check("scene.kmpt", hasattr(bpy.types.Scene, "kmpt"))

# Panels actually registered with Blender's RNA
panels = [c.__name__ for c in bpy.types.Panel.__subclasses__()
          if getattr(c, "bl_category", "") in ("KMP", "MKW", "Mario Kart Wii")
          or c.__name__ in ("KMPUtilities", "KCLUtilities", "AREAUtilities",
                            "CAMEUtilities", "RouteUtilities", "MaterialUtilities",
                            "ShaderUtilities")]
check("panels_registered", len(panels))

# Operators callable
ops = [o for o in dir(bpy.ops.kmpt)] if hasattr(bpy.ops, "kmpt") else []
check("kmpt_operators", len(ops))

# Principled socket handling -  the 4.0/5.0 index reshuffle
m = bpy.data.materials.new("verify_mat")
m.use_nodes = True
p = [n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'][0]
p.inputs['Metallic'].default_value = 1.0
mod._principled_set(m, 'Metallic', 0.0)
check("metallic_zeroed", p.inputs['Metallic'].default_value == 0.0)
check("spec_socket_name", mod.SPECULAR_SOCKET)
check("spec_applied", mod._principled_set(m, mod.SPECULAR_SOCKET, 0))
# Ensure we did NOT clobber Normal (the 5.x index-5 trap)
check("normal_untouched", not p.inputs['Normal'].is_linked)

# Node groups build without error
try:
    mod.create_node_groups()
    check("node_groups", True)
except Exception:
    traceback.print_exc()
    check("node_groups", False)

# OBJ exporter normals path (calc_normals_split removal in 4.1)
try:
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.active_object
    out = "/tmp/_verify_export.obj"
    mod.export_obj.save(
        bpy.context, out,
        use_selection=True, use_normals=True, use_uvs=True,
        use_materials=False, use_triangles=True,
    )
    check("obj_export", os.path.exists(out) and os.path.getsize(out) > 0)
    if os.path.exists(out):
        txt = open(out).read()
        check("obj_has_normals", "vn " in txt)
except Exception:
    traceback.print_exc()
    check("obj_export", False)

try:
    addon_utils.disable(name)
    check("disable_clean", True)
except Exception:
    traceback.print_exc()
    check("disable_clean", False)

print("=== RESULTS ===")
for k, v in results.items():
    print(f"  {k} = {v}")
bad = [k for k, v in results.items()
       if v is False or (isinstance(v, int) and not isinstance(v, bool) and v == 0)]
print("VERDICT:", "PASS" if not bad else "FAIL " + ",".join(bad))
