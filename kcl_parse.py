"""Strict KCL parser per the mkwiiki spec.

Validates a KCL independently of Wiimms' tools, the way a third-party editor
would.

Header (0x3c):
  0x00 u32 pos_data_offset     0-indexed
  0x04 u32 nrm_data_offset     0-indexed
  0x08 u32 prism_data_offset   stored 0x10 LESS than actual (1-indexed)
  0x0c u32 block_data_offset
  0x10 f32 prism_thickness
  0x14 Vec3 area_min_pos
  0x20/24/28 u32 masks
  0x2c/30/34 u32 shifts
  0x38 f32 sphere_radius (MKW expects this)
"""
import struct
import sys


def parse(path, verbose=True):
    d = open(path, "rb").read()
    (pos_off, nrm_off, prism_off, block_off) = struct.unpack(">4I", d[:16])
    thickness = struct.unpack(">f", d[0x10:0x14])[0]
    area_min = struct.unpack(">3f", d[0x14:0x20])
    masks = struct.unpack(">3I", d[0x20:0x2C])
    shifts = struct.unpack(">3I", d[0x2C:0x38])
    sphere = struct.unpack(">f", d[0x38:0x3C])[0] if len(d) >= 0x3C else None

    out = {
        "file": path,
        "size": len(d),
        "pos_off": pos_off,
        "nrm_off": nrm_off,
        "prism_off_stored": prism_off,
        "prism_off_actual": prism_off + 0x10,
        "block_off": block_off,
        "thickness": thickness,
        "area_min": area_min,
        "masks": [hex(m) for m in masks],
        "shifts": shifts,
        "sphere_radius": sphere,
    }

    errors = []

    # Section sizes (sections may appear in any order, but Wiimm writes them in order)
    n_pos = (nrm_off - pos_off) // 12
    n_nrm = ((prism_off + 0x10) - nrm_off) // 12
    out["n_positions"] = n_pos
    out["n_normals"] = n_nrm

    if pos_off < 0x3C:
        errors.append("pos_data_offset (0x%x) overlaps the 0x3c header" % pos_off)
    if not (pos_off < nrm_off < prism_off + 0x10 <= block_off):
        errors.append("sections not in ascending order")

    # Walk the octree to find the highest prism index actually referenced.
    prism_actual = prism_off + 0x10
    max_idx = 0
    seen_leaves = 0

    def walk(base, depth=0):
        nonlocal max_idx, seen_leaves
        if depth > 12:
            return
        for i in range(8):
            p = base + i * 4
            if p + 4 > len(d):
                return
            off = struct.unpack(">I", d[p:p + 4])[0]
            if off & 0x80000000:
                lp = base + (off & 0x7FFFFFFF)
                seen_leaves += 1
                # u16 list, 0-terminated, 1-based indices
                while lp + 2 <= len(d):
                    v = struct.unpack(">H", d[lp:lp + 2])[0]
                    lp += 2
                    if v == 0:
                        break
                    max_idx = max(max_idx, v)
            else:
                walk(base + off, depth + 1)

    walk(block_off)
    out["octree_leaves"] = seen_leaves
    out["max_prism_index_from_octree"] = max_idx
    # Authoritative count: section 3 runs from prism_actual up to the next
    # section start (Wiimm writes sections in ascending order).
    n_prisms = (block_off - prism_actual) // 0x10
    out["n_prisms"] = n_prisms
    max_idx = n_prisms

    # Read the prisms and resolve their vertices
    tris = []
    flags = {}
    for i in range(1, max_idx + 1):
        p = prism_actual + (i - 1) * 0x10
        if p + 0x10 > len(d):
            errors.append("prism %d runs past EOF" % i)
            break
        height, pos_i, fnrm_i, e1, e2, e3, attr = struct.unpack(">fHHHHHH", d[p:p + 0x10])
        if pos_off + pos_i * 12 + 12 > len(d):
            errors.append("prism %d position index %d out of range" % (i, pos_i))
            continue
        for ni, nname in ((fnrm_i, "fnrm"), (e1, "e1"), (e2, "e2"), (e3, "e3")):
            if ni >= n_nrm:
                errors.append("prism %d %s index %d >= n_normals %d" % (i, nname, ni, n_nrm))
        v = struct.unpack(">3f", d[pos_off + pos_i * 12: pos_off + pos_i * 12 + 12])
        tris.append((v, attr, height))
        flags[attr] = flags.get(attr, 0) + 1

    out["flags"] = {hex(k): v for k, v in sorted(flags.items())}
    if tris:
        xs = [t[0][0] for t in tris]
        ys = [t[0][1] for t in tris]
        zs = [t[0][2] for t in tris]
        out["bbox_min"] = (min(xs), min(ys), min(zs))
        out["bbox_max"] = (max(xs), max(ys), max(zs))
        out["extent"] = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
        # sanity: vertex 0 is where Wiimm writes its signature
        v0 = struct.unpack(">3f", d[pos_off:pos_off + 12])
        out["vertex0_raw"] = v0
        out["vertex0_is_ascii"] = d[pos_off:pos_off + 8].isascii() and d[pos_off:pos_off + 8].isalpha()

    out["errors"] = errors
    if verbose:
        for k, val in out.items():
            print(f"  {k} = {val}")
    return out


if __name__ == "__main__":
    for f in sys.argv[1:]:
        print("=" * 60)
        parse(f)
