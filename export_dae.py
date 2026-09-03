# SPDX-License-Identifier: GPL-2.0-or-later
"""COLLADA (.dae) export.

Blender's Collada exporter was removed in 5.0 and the bundled Autodesk
FbxConverter is Windows-only, so this writes the COLLADA 1.4.1 subset needed
for static meshes directly.

Geometry is emitted as <triangles>, one group per material. BrawlCrate builds
one MDL0 material per group and reads its texture from the sampler chain.
"""

import os
import shutil

import bpy
import bmesh
from mathutils import Matrix

# Blender is Z-up, COLLADA is Y-up.
_Z_UP_TO_Y_UP = Matrix(((1, 0, 0, 0),
                        (0, 0, 1, 0),
                        (0, -1, 0, 0),
                        (0, 0, 0, 1)))

_MISSING_MATERIAL = "MKWU_no_material"
_UV_SEMANTIC = "UVMap"

def _fmt(value):
    """Compact fixed-point float; COLLADA parsers dislike exponent notation."""
    text = "%.6f" % value
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"

def _xml_escape(text):
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))

def _safe_id(text, used):
    """COLLADA ids must be NCNames: no spaces, not starting with a digit."""
    out = []
    for ch in text:
        out.append(ch if (ch.isalnum() or ch in "_-") else "_")
    ident = "".join(out) or "id"
    if not (ident[0].isalpha() or ident[0] == "_"):
        ident = "_" + ident
    base, n = ident, 1
    while ident in used:
        ident = "%s_%d" % (base, n)
        n += 1
    used.add(ident)
    return ident

def _ensure_loop_normals(me):
    """Populate loop.normal.

    Up to 4.0 the split-normal cache is empty until calc_normals_split() is
    called and loop.normal reads back as a zero vector. The method was removed
    in 4.1, where the data is always available.
    """
    if hasattr(me, "calc_normals_split"):
        me.calc_normals_split()

def material_image(mat):
    """First image texture feeding a material's node tree, or None."""
    if mat is None or not getattr(mat, "use_nodes", False):
        return None

    # Prefer the image linked to Base Color.
    for node in mat.node_tree.nodes:
        if node.bl_idname != "ShaderNodeBsdfPrincipled":
            continue
        socket = node.inputs.get("Base Color")
        if socket is None or not socket.is_linked:
            continue
        source = socket.links[0].from_node
        if source.bl_idname == "ShaderNodeTexImage" and source.image:
            return source.image

    for node in mat.node_tree.nodes:
        if node.bl_idname == "ShaderNodeTexImage" and node.image:
            return node.image
    return None

def strip_duplicate_suffix(name):
    """Remove Blender's .001 style uniquifying suffixes.

    These appear trailing on a datablock name (d64_road.png.001) and interior
    in a filename on disk (d64_road.png.001.png), and break texture references
    downstream. Only exactly three digits count, matching Blender. A repeated
    extension left behind by the strip is collapsed.
    """
    if not name:
        return name

    parts = name.split(".")
    kept = [parts[0]]
    for part in parts[1:]:
        if len(part) == 3 and part.isdigit():
            continue
        kept.append(part)

    # Collapse an extension duplicated by the strip.
    while len(kept) > 2 and kept[-1].lower() == kept[-2].lower():
        kept.pop()

    result = ".".join(kept)
    return result if result.strip(".") else name

def image_identity(image):
    """Key identifying the underlying image, ignoring datablock naming.

    Two datablocks pointing at the same file are the same texture even though
    Blender named the second one foo.png.001.
    """
    try:
        path = image.filepath_from_user() if image.filepath else ""
    except (RuntimeError, ValueError):
        path = ""
    if path:
        return "file:" + os.path.normcase(os.path.abspath(path))
    # Packed or generated: fall back to the de-suffixed datablock name.
    return "name:" + strip_duplicate_suffix(image.name)

def _image_filename(image):
    """On-disk filename to reference from the DAE, without Blender suffixes."""
    try:
        name = os.path.basename(image.filepath_from_user()) if image.filepath else ""
    except (RuntimeError, ValueError):
        name = ""
    if not name:
        name = image.name
    name = strip_duplicate_suffix(name)
    if not os.path.splitext(name)[1]:
        ext = (image.file_format or "PNG").lower()
        name += ".png" if ext in ("", "png") else "." + ext
    return name

def resolve_images(materials):
    """Map material key to image, collapsing duplicate datablocks.

    Returns (images, filenames, conflicts). conflicts lists files that had to
    be renamed because two different ones shared a name once de-suffixed.
    """
    canonical = {}
    images = {}
    for key, mat in materials:
        image = material_image(mat)
        if image is None:
            continue
        identity = image_identity(image)
        # First datablock seen for an identity wins.
        canonical.setdefault(identity, image)
        images[key] = canonical[identity]

    filenames, taken, conflicts = {}, {}, []
    for identity, image in canonical.items():
        name = _image_filename(image)
        owner = taken.get(name)
        if owner is not None and owner != identity:
            # Different files that collide once de-suffixed must stay apart.
            stem, ext = os.path.splitext(name)
            n = 1
            while "%s_%d%s" % (stem, n, ext) in taken:
                n += 1
            name = "%s_%d%s" % (stem, n, ext)
            conflicts.append(name)
        taken[name] = identity
        filenames[identity] = name
    return images, filenames, conflicts

def copy_images(images, directory, filenames=None):
    """Write ``images`` next to the DAE. Returns (written, failed)."""
    written, failed = [], []
    for image in images:
        if filenames is not None:
            name = filenames[image_identity(image)]
        else:
            name = _image_filename(image)
        dest = os.path.join(directory, name)
        try:
            source = image.filepath_from_user() if image.filepath else ""
            if source and os.path.isfile(source):
                if os.path.abspath(source) != os.path.abspath(dest):
                    shutil.copyfile(source, dest)
            else:
                # Packed or generated: save a copy without touching the original.
                copy = image.copy()
                try:
                    copy.filepath_raw = dest
                    if not copy.file_format:
                        copy.file_format = "PNG"
                    copy.save()
                finally:
                    bpy.data.images.remove(copy)
            written.append(name)
        except Exception:
            failed.append(image.name)
    return written, failed

def _source(sid, values, params):
    stride = len(params)
    return (
        '<source id="{sid}">'
        '<float_array id="{sid}-array" count="{count}">{data}</float_array>'
        '<technique_common>'
        '<accessor source="#{sid}-array" count="{n}" stride="{stride}">'
        '{params}'
        '</accessor></technique_common></source>'
    ).format(
        sid=sid, count=len(values), n=len(values) // stride, stride=stride,
        data=" ".join(_fmt(v) for v in values),
        params="".join('<param name="%s" type="float"/>' % p for p in params),
    )

def _gather(objects, depsgraph, matrix):
    """Evaluate objects to triangulated meshes, grouped by material."""
    meshes = []
    used_ids = set()

    for ob in objects:
        if ob.type != "MESH":
            continue

        eval_ob = ob.evaluated_get(depsgraph)
        try:
            me = eval_ob.to_mesh()
        except RuntimeError:
            continue
        if me is None:
            continue

        try:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            bm.to_mesh(me)
            bm.free()

            me.transform(matrix @ ob.matrix_world)
            if ob.matrix_world.determinant() < 0.0:
                me.flip_normals()

            me.calc_loop_triangles()
            _ensure_loop_normals(me)

            if not me.loop_triangles:
                continue

        
            slot_materials = [s.material for s in ob.material_slots]

            uv_data = me.uv_layers.active.data if me.uv_layers.active else None

            positions = []
            for vert in me.vertices:
                positions.extend(vert.co[:])

            # One group per material, so BrawlCrate creates one MDL0
            # material per group instead of collapsing them.
            groups = {}
            normals, uvs = [], []
            corner = 0
            for tri in me.loop_triangles:
                index = tri.material_index
                mat = slot_materials[index] if index < len(slot_materials) else None
                key = (strip_duplicate_suffix(mat.name)
                       if mat is not None else _MISSING_MATERIAL)

                entry = groups.setdefault(key, {"material": mat, "indices": []})
                for vert_index, loop_index in zip(tri.vertices, tri.loops):
                    normals.extend(me.loops[loop_index].normal[:])
                    if uv_data is not None:
                        uvs.extend(uv_data[loop_index].uv[:])
                    entry["indices"].append((vert_index, corner))
                    corner += 1

            meshes.append({
                "id": _safe_id(strip_duplicate_suffix(ob.name), used_ids),
                "name": strip_duplicate_suffix(ob.name),
                "positions": positions,
                "normals": normals,
                "uvs": uvs,
                "groups": groups,
                "has_uv": uv_data is not None,
            })
        finally:
            eval_ob.to_mesh_clear()

    return meshes

def write_dae(filepath, objects, global_scale=1.0, y_up=True,
              copy_textures=False):
    """Write ``objects`` to ``filepath`` as COLLADA 1.4.1.

    Returns ``(mesh_count, triangle_count, texture_names)``.
    """
    matrix = Matrix.Scale(global_scale, 4)
    if y_up:
        matrix = _Z_UP_TO_Y_UP @ matrix

    depsgraph = bpy.context.evaluated_depsgraph_get()
    meshes = _gather(objects, depsgraph, matrix)

    materials = []
    for mesh in meshes:
        for key in mesh["groups"]:
            if key not in [m[0] for m in materials]:
                materials.append((key, mesh["groups"][key]["material"]))

    used_ids = set()
    mat_ids = {}
    for key, mat in materials:
        # Strip .001 so a duplicated material is not a second MDL0 material.
        mat_ids[key] = _safe_id(strip_duplicate_suffix(key), used_ids)

    images, image_filenames, conflicts = resolve_images(materials)

    image_ids, seen_images = {}, {}
    for key, image in images.items():
        identity = image_identity(image)
        if identity not in seen_images:
            stem = os.path.splitext(image_filenames[identity])[0]
            # Namespaced so image ids cannot collide with material ids.
            seen_images[identity] = _safe_id(stem + "-image", used_ids)
        image_ids[key] = seen_images[identity]

    out = [
        '<?xml version="1.0" encoding="utf-8"?>',
        '<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" '
        'version="1.4.1">',
        '<asset>'
        '<contributor><authoring_tool>MKW Utilities</authoring_tool></contributor>'
        '<unit name="meter" meter="1"/>'
        '<up_axis>%s</up_axis>'
        '</asset>' % ("Y_UP" if y_up else "Z_UP"),
    ]

    if seen_images:
        out.append("<library_images>")
        emitted = set()
        for key, image in images.items():
            iid = image_ids[key]
            if iid in emitted:
                continue
            emitted.add(iid)
            filename = image_filenames[image_identity(image)]
            out.append('<image id="%s" name="%s"><init_from>%s</init_from></image>'
                       % (iid, iid, _xml_escape(filename)))
        out.append("</library_images>")

    out.append("<library_effects>")
    for key, mat in materials:
        mid = mat_ids[key]
        if key in image_ids:
            iid = image_ids[key]
            out.append(
                '<effect id="%s-effect"><profile_COMMON>'
                '<newparam sid="%s-surface"><surface type="2D">'
                '<init_from>%s</init_from></surface></newparam>'
                '<newparam sid="%s-sampler"><sampler2D>'
                '<source>%s-surface</source></sampler2D></newparam>'
                '<technique sid="common"><lambert>'
                '<emission><color sid="emission">0 0 0 1</color></emission>'
                '<diffuse><texture texture="%s-sampler" texcoord="%s"/></diffuse>'
                '</lambert></technique>'
                '</profile_COMMON></effect>'
                % (mid, iid, iid, iid, iid, iid, _UV_SEMANTIC))
        else:
            out.append(
                '<effect id="%s-effect"><profile_COMMON><technique sid="common">'
                '<lambert>'
                '<emission><color sid="emission">0 0 0 1</color></emission>'
                '<diffuse><color sid="diffuse">0.8 0.8 0.8 1</color></diffuse>'
                '</lambert>'
                '</technique></profile_COMMON></effect>' % mid)
    out.append("</library_effects>")

    out.append("<library_materials>")
    for key, mat in materials:
        out.append(
            '<material id="%s" name="%s">'
            '<instance_effect url="#%s-effect"/></material>'
            % (mat_ids[key], _xml_escape(key), mat_ids[key]))
    out.append("</library_materials>")

    total_tris = 0
    out.append("<library_geometries>")
    for mesh in meshes:
        gid = mesh["id"]
        out.append('<geometry id="%s-geometry" name="%s"><mesh>'
                   % (gid, _xml_escape(mesh["name"])))

        out.append(_source("%s-positions" % gid, mesh["positions"],
                           ("X", "Y", "Z")))
        out.append(_source("%s-normals" % gid, mesh["normals"], ("X", "Y", "Z")))
        if mesh["has_uv"]:
            out.append(_source("%s-uvs" % gid, mesh["uvs"], ("S", "T")))

        out.append('<vertices id="%s-vertices">'
                   '<input semantic="POSITION" source="#%s-positions"/>'
                   '</vertices>' % (gid, gid))

        inputs = ('<input semantic="VERTEX" source="#%s-vertices" offset="0"/>'
                  '<input semantic="NORMAL" source="#%s-normals" offset="1"/>'
                  % (gid, gid))
        if mesh["has_uv"]:
            inputs += ('<input semantic="TEXCOORD" source="#%s-uvs" '
                       'offset="1" set="0"/>' % gid)

        for key, entry in mesh["groups"].items():
            flat = []
            for vert_index, corner in entry["indices"]:
                flat.append(str(vert_index))
                flat.append(str(corner))
            count = len(entry["indices"]) // 3
            total_tris += count
            out.append(
                '<triangles material="%s" count="%d">%s<p>%s</p></triangles>'
                % (mat_ids[key], count, inputs, " ".join(flat)))

        out.append("</mesh></geometry>")
    out.append("</library_geometries>")

    out.append('<library_visual_scenes><visual_scene id="Scene" name="Scene">')
    for mesh in meshes:
        gid = mesh["id"]
        binds = "".join(
            '<instance_material symbol="%s" target="#%s">'
            '<bind_vertex_input semantic="%s" input_semantic="TEXCOORD" '
            'input_set="0"/></instance_material>'
            % (mat_ids[key], mat_ids[key], _UV_SEMANTIC)
            for key in mesh["groups"])
        out.append(
            '<node id="%s" name="%s" type="NODE">'
            '<instance_geometry url="#%s-geometry">'
            '<bind_material><technique_common>%s</technique_common></bind_material>'
            '</instance_geometry></node>'
            % (gid, _xml_escape(mesh["name"]), gid, binds))
    out.append("</visual_scene></library_visual_scenes>")
    out.append('<scene><instance_visual_scene url="#Scene"/></scene>')
    out.append("</COLLADA>")

    with open(filepath, "w", encoding="utf-8") as handle:
        handle.write("\n".join(out))

    written = []
    if copy_textures and seen_images:
        unique = {}
        for image in images.values():
            unique[image_identity(image)] = image
        written, _failed = copy_images(unique.values(),
                                       os.path.dirname(os.path.abspath(filepath)),
                                       filenames=image_filenames)

    return len(meshes), total_tris, written, conflicts
