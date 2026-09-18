"""Collada export checks for MKW Utilities.

Run: blender -b --factory-startup --python dae_test.py -- <addon dir>
"""
import os
import sys
import math
import shutil
import tempfile
import xml.etree.ElementTree as ET

import bpy
import addon_utils

NS = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
TEXDIR = tempfile.gettempdir()
FAILURES = []


def check(name, ok, detail=""):
    print("%-42s %s %s" % (name, "PASS" if ok else "FAIL", detail))
    if not ok:
        FAILURES.append(name)


def install(src):
    target_root = bpy.utils.user_resource("SCRIPTS", path="addons", create=True)
    target = os.path.join(target_root, "Blender-MKW-Utilities")
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(src, target)
    addon_utils.modules_refresh()
    addon_utils.enable("Blender-MKW-Utilities", default_set=True)
    return sys.modules["Blender-MKW-Utilities"]


def build_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    bpy.ops.mesh.primitive_monkey_add()
    head = bpy.context.active_object
    head.name = "course map"          # space: must be sanitised in the id
    # Two textured materials assigned per-face: each must survive as its own
    # <triangles> group, or BrawlCrate collapses them into one MDL0 material.
    for name in ("road mat", "boost mat"):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        img = bpy.data.images.new(name.replace(" ", "_") + "_tex", 8, 8)
        img.filepath_raw = os.path.join(TEXDIR, img.name + ".png")
        img.file_format = "PNG"
        img.save()
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        head.data.materials.append(mat)
    for i, poly in enumerate(head.data.polygons):
        poly.material_index = i % 2
    head.data.uv_layers.new()

    bpy.ops.mesh.primitive_cube_add(location=(4, 0, 0))
    box = bpy.context.active_object
    box.name = "wall"
    box.data.materials.append(bpy.data.materials.new("wall/mat"))

    bpy.ops.mesh.primitive_plane_add(location=(-4, 0, 0))
    plane = bpy.context.active_object
    plane.name = "no_material"       # deliberately left without a material

    bpy.ops.object.select_all(action="SELECT")
    return head, box, plane


def main():
    src = sys.argv[sys.argv.index("--") + 1]
    mod = install(src)
    out = tempfile.mkdtemp(prefix="mkwu_dae_")
    globals()["TEXDIR"] = out

    check("module imports export_dae", hasattr(mod, "export_dae"))
    check("operator registered", hasattr(bpy.ops.export, "autodesk_dae"))

    build_scene()
    path = os.path.join(out, "scene.dae")
    options = mod.ColladaExportOptions(filepath=path, daeExportScale=100)
    reports = []
    result = mod.export_collada(
        bpy.context, options, lambda level, message: reports.append((level, message)))
    check("result dict reports success", result["ok"] is True)
    check("result dict object count", result["objects"] == 3,
          str(result.get("objects")))
    check("result dict triangle count", result["triangles"] > 0,
          str(result.get("triangles")))
    check("result dict skipped names", result["skipped_objects"] == [],
          str(result.get("skipped_objects")))
    check("result dict export method", result["method"] == "builtin",
          str(result.get("method")))
    check("file written", os.path.isfile(path))

    root = ET.parse(path).getroot()

    tris = root.findall(".//c:triangles", NS)
    poly = root.findall(".//c:polylist", NS)
    # 2 groups on the monkey (one per material) + cube + plane.
    check("one <triangles> per material", len(tris) == 4, "count=%d" % len(tris))
    check("emits no <polylist>", not poly)

    syms = [t.get("material") for t in tris]
    check("material groups distinct", len(set(syms)) == 4, str(syms))

    imgs = root.findall(".//c:library_images/c:image", NS)
    check("library_images present", len(imgs) == 2, "count=%d" % len(imgs))

    samplers = root.findall(".//c:sampler2D", NS)
    surfaces = root.findall(".//c:surface", NS)
    check("sampler2D per texture", len(samplers) == 2, "count=%d" % len(samplers))
    check("surface per texture", len(surfaces) == 2, "count=%d" % len(surfaces))

    tex_refs = [t.get("texture") for t in root.findall(".//c:texture", NS)]
    check("effects reference samplers",
          all(t and t.endswith("-sampler") for t in tex_refs) and len(tex_refs) == 2,
          str(tex_refs))

    binds = root.findall(".//c:bind_vertex_input", NS)
    check("bind_vertex_input present", len(binds) >= 2, "count=%d" % len(binds))

    copied = [f for f in os.listdir(out) if f.endswith(".png")]
    check("textures copied beside dae", len(copied) == 2, str(sorted(copied)))

    for img in imgs:
        ref = img.find("c:init_from", NS).text
        check("image %s exists on disk" % ref, os.path.isfile(os.path.join(out, ref)))

    geoms = root.findall(".//c:geometry", NS)
    check("all meshes exported", len(geoms) == 3, "count=%d" % len(geoms))

    mats = root.findall(".//c:material", NS)
    check("materials incl. placeholder", len(mats) == 4, "count=%d" % len(mats))

    ids = [g.get("id") for g in geoms]
    check("ids are valid NCNames",
          all(i and " " not in i and "/" not in i and not i[0].isdigit()
              for i in ids), str(ids))

    # Normals must be unit length. Before the 4.0 fix these were all zero.
    arrays = [a for a in root.findall(".//c:float_array", NS)
              if "normals" in (a.get("id") or "")]
    check("normal sources present", len(arrays) == 3)
    worst = 1.0
    for arr in arrays:
        vals = [float(x) for x in arr.text.split()]
        for i in range(0, len(vals), 3):
            length = math.sqrt(vals[i] ** 2 + vals[i + 1] ** 2 + vals[i + 2] ** 2)
            worst = min(worst, length)
    check("normals are unit length", worst > 0.99, "min=%.4f" % worst)

    # Scale must reach the file: default cube is 2m, at x100 it spans 200.
    pos = [a for a in root.findall(".//c:float_array", NS)
           if "positions" in (a.get("id") or "")]
    vals = [float(x) for x in pos[0].text.split()]
    check("scale applied", max(abs(v) for v in vals) > 100,
          "max=%.1f" % max(abs(v) for v in vals))

    # Selection-only export.
    bpy.ops.object.select_all(action="DESELECT")
    bpy.data.objects["wall"].select_set(True)
    sel = os.path.join(out, "sel.dae")
    bpy.ops.export.autodesk_dae("EXEC_DEFAULT", filepath=sel,
                                daeExportSelection=True)
    sel_geoms = ET.parse(sel).getroot().findall(".//c:geometry", NS)
    check("selection only", len(sel_geoms) == 1, "count=%d" % len(sel_geoms))

    # Untextured export must still be valid.
    notex = os.path.join(out, "notex.dae")
    bpy.ops.object.select_all(action="DESELECT")
    bpy.data.objects["no_material"].select_set(True)
    bpy.ops.export.autodesk_dae("EXEC_DEFAULT", filepath=notex,
                                daeExportSelection=True,
                                daeExportCopyTextures=True)
    nroot = ET.parse(notex).getroot()
    check("untextured export valid",
          len(nroot.findall(".//c:triangles", NS)) == 1
          and not nroot.findall(".//c:library_images/c:image", NS))

    # Empty selection must cancel, not write a broken file.
    bpy.ops.object.select_all(action="DESELECT")
    empty = os.path.join(out, "empty.dae")
    try:
        res = bpy.ops.export.autodesk_dae("EXEC_DEFAULT", filepath=empty,
                                          daeExportSelection=True)
        cancelled = res == {"CANCELLED"}
    except RuntimeError as exc:
        # EXEC_DEFAULT turns a reported error into an exception.
        cancelled = "Nothing to export" in str(exc)
    check("empty selection cancels", cancelled)
    check("no file on cancel", not os.path.isfile(empty))
    reports = []
    failed = mod.export_collada(
        bpy.context,
        mod.ColladaExportOptions(filepath=empty, daeExportSelection=True),
        lambda level, message: reports.append((level, message)),
    )
    common = {"ok", "filepath", "objects", "triangles",
              "skipped_objects", "error"}
    check("failure result has stable schema", common <= set(failed), str(failed))
    check("failure result reports error",
          failed["ok"] is False and bool(failed["error"]), str(failed))

    check("FbxConverter absent here", mod.fbx_converter_path() is None)

    shutil.rmtree(out, ignore_errors=True)
    # --- Blender .001 suffix handling -------------------------------------
    mod.export_dae  # ensure loaded
    strip = mod.export_dae.strip_duplicate_suffix
    check("strip trailing .001", strip("d64_road.png.001") == "d64_road.png")
    # The real-world case: the suffix is INTERIOR, inside the filename on disk.
    check("strip interior .001",
          strip("d64_road.png.001.png") == "d64_road.png",
          strip("d64_road.png.001.png"))
    check("strip repeated", strip("t.png.001.002") == "t.png")
    check("strip interior multi", strip("tex.001.002.png") == "tex.png")
    check("keep real extension", strip("road.png") == "road.png")
    check("keep short numeric", strip("a.1") == "a.1")
    check("keep 4-digit", strip("a.0001") == "a.0001")
    check("keep dotted name", strip("my.file.name.png") == "my.file.name.png")
    check("keep trailing digits in stem",
          strip("Custom Offroad 2_0.png") == "Custom Offroad 2_0.png")

    # A texture whose file on disk carries the suffix must export clean.
    interior = os.path.join(out, "interior")
    os.makedirs(interior, exist_ok=True)
    seedi = bpy.data.images.new("seedi", 8, 8)
    seedi.filepath_raw = os.path.join(interior, "d64_road.png.001.png")
    seedi.file_format = "PNG"
    seedi.save()
    bpy.data.images.remove(seedi)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.mesh.primitive_plane_add()
    plane = bpy.context.active_object
    imat = bpy.data.materials.new("dirt road")
    imat.use_nodes = True
    iimg = bpy.data.images.load(os.path.join(interior, "d64_road.png.001.png"))
    inode = imat.node_tree.nodes.new("ShaderNodeTexImage")
    inode.image = iimg
    imat.node_tree.links.new(
        inode.outputs["Color"],
        imat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    plane.data.materials.append(imat)
    plane.data.uv_layers.new()
    bpy.ops.object.select_all(action="SELECT")

    ipath = os.path.join(interior, "i.dae")
    bpy.ops.export.autodesk_dae("EXEC_DEFAULT", filepath=ipath,
                                daeExportCopyTextures=True)
    iroot = ET.parse(ipath).getroot()
    irefs = [i.find("c:init_from", NS).text
             for i in iroot.findall(".//c:library_images/c:image", NS)]
    check("interior suffix cleaned in dae", irefs == ["d64_road.png"], str(irefs))
    ipngs = sorted(f for f in os.listdir(interior) if f.endswith(".png"))
    check("texture copied under clean name", "d64_road.png" in ipngs, str(ipngs))

    # Two datablocks pointing at the SAME file must collapse to one image.
    dup = os.path.join(out, "dup")
    os.makedirs(dup, exist_ok=True)
    seed = bpy.data.images.new("seed", 8, 8)
    seed.filepath_raw = os.path.join(dup, "shared.png")
    seed.file_format = "PNG"
    seed.save()
    bpy.data.images.remove(seed)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.active_object
    cube.name = "dupcourse"
    for _ in range(2):
        mat = bpy.data.materials.new("shared mat")
        mat.use_nodes = True
        img = bpy.data.images.load(os.path.join(dup, "shared.png"))
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        mat.node_tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
        cube.data.materials.append(mat)
    for i, poly in enumerate(cube.data.polygons):
        poly.material_index = i % 2
    cube.data.uv_layers.new()

    names = [i.name for i in bpy.data.images if "shared" in i.name]
    check("blender created a .001 datablock",
          any(n.endswith(".001") for n in names), str(names))

    bpy.ops.object.select_all(action="SELECT")
    dpath = os.path.join(dup, "dup.dae")
    bpy.ops.export.autodesk_dae("EXEC_DEFAULT", filepath=dpath,
                                daeExportCopyTextures=True)
    droot = ET.parse(dpath).getroot()
    dimgs = droot.findall(".//c:library_images/c:image", NS)
    refs = [i.find("c:init_from", NS).text for i in dimgs]
    check("duplicate image datablocks collapse", len(dimgs) == 1, str(refs))
    check("no .001 in init_from",
          all(".001" not in r for r in refs), str(refs))
    dmats = [m.get("name") for m in droot.findall(".//c:material", NS)]
    check("no .001 in material names",
          all(".001" not in m for m in dmats), str(dmats))
    ids = [i.get("id") for i in dimgs] + [m.get("id") for m in
                                          droot.findall(".//c:material", NS)]
    check("no _001 in ids", all("_001" not in i for i in ids), str(ids))
    pngs = [f for f in os.listdir(dup) if f.endswith(".png")]
    check("one texture written", len(pngs) == 1, str(pngs))

    print("VERDICT: %s" % ("PASS" if not FAILURES else "FAIL " + ",".join(FAILURES)))
    if FAILURES:
        raise SystemExit(1)


main()
