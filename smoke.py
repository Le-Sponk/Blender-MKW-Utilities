"""Minimal registration check — works on both baseline and fixed code."""
import bpy, addon_utils, shutil, os, sys, traceback

argv = sys.argv
src = argv[argv.index("--") + 1]
name = os.path.basename(src.rstrip("/"))
d = bpy.utils.user_resource('SCRIPTS', path="addons", create=True)
t = os.path.join(d, name)
shutil.rmtree(t, ignore_errors=True)
shutil.copytree(src, t)
addon_utils.modules_refresh()

print("BLENDER", bpy.app.version_string)
try:
    addon_utils.enable(name, default_set=True)
except Exception as e:
    print("ENABLE_EXC", type(e).__name__, e)

print("ENABLED", name in bpy.context.preferences.addons)
print("SCENE_KMPT", hasattr(bpy.types.Scene, "kmpt"))
panels = [c.__name__ for c in bpy.types.Panel.__subclasses__()
          if c.__name__ in ("KMPUtilities", "KCLUtilities", "AREAUtilities",
                            "CAMEUtilities", "RouteUtilities",
                            "MaterialUtilities", "ShaderUtilities")]
print("PANELS", len(panels))
print("OPS", len(dir(bpy.ops.kmpt)) if hasattr(bpy.ops, "kmpt") else 0)

unreg_ok = True
try:
    addon_utils.disable(name)
except Exception as e:
    unreg_ok = False
    print("DISABLE_EXC", type(e).__name__, e)
print("DISABLE_CLEAN", unreg_ok)
