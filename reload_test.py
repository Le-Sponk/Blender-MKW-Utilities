"""Verify submodules reload when the add-on is updated in place.

Blender keeps submodules in sys.modules across a disable/enable cycle. Without
an explicit reload, installing a new version over an old one leaves the previous
code live until Blender restarts, and calls into it fail with stale signatures.

Run: blender -b --factory-startup --python reload_test.py -- <old zip> <new dir>
"""
import os
import sys
import inspect
import shutil

import bpy
import addon_utils

FAILURES = []


def check(name, ok, detail=""):
    print("%-46s %s %s" % (name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILURES.append(name)


def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    old_zip, new_dir = args[0], args[1]

    mid = "bl_ext.user_default.mkw_utilities"

    bpy.ops.extensions.package_install_files(
        filepath=old_zip, repo="user_default", enable_on_install=True)
    old_sig = str(inspect.signature(sys.modules[mid].export_dae.write_dae))
    check("old build installed", mid in sys.modules, old_sig)

    cached = [k for k in sys.modules if k.startswith(mid)]
    check("submodules cached", len(cached) > 1, str(len(cached)))

    addon_utils.disable(mid, default_set=True)
    still = [k for k in sys.modules if k.startswith(mid)]
    check("submodules survive disable", bool(still),
          "%d still cached" % len(still))

    # Update the files in place, as installing a new version does.
    dest = os.path.dirname(sys.modules[mid].__file__)
    for name in ("__init__.py", "export_dae.py", "export_obj.py"):
        shutil.copyfile(os.path.join(new_dir, name), os.path.join(dest, name))

    addon_utils.enable(mid, default_set=True)
    new_sig = str(inspect.signature(sys.modules[mid].export_dae.write_dae))
    check("submodule reloaded after update", new_sig != old_sig,
          "%s -> %s" % (old_sig, new_sig))
    check("new keyword available", "copy_textures" in new_sig, new_sig)

    # The call that failed for real.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.active_object
    ob.data.materials.append(bpy.data.materials.new("m"))
    ob.data.uv_layers.new()
    bpy.ops.object.select_all(action="SELECT")

    import tempfile
    out = os.path.join(tempfile.mkdtemp(), "reload.dae")
    for copy_textures in (True, False):
        try:
            res = bpy.ops.export.autodesk_dae(
                "EXEC_DEFAULT", filepath=out, daeExportMethod='BUILTIN',
                daeExportCopyTextures=copy_textures)
            ok = res == {"FINISHED"} and os.path.isfile(out)
            detail = ""
        except (RuntimeError, TypeError) as exc:
            ok, detail = False, str(exc)
        check("export after update (copy_textures=%s)" % copy_textures,
              ok, detail)

    print("VERDICT: %s" % ("PASS" if not FAILURES else "FAIL " + ",".join(FAILURES)))


main()
