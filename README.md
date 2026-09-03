# Blender MKW Utilities (unofficial update)

A Blender add-on for creating Mario Kart Wii custom courses (KMP / KCL authoring).

This is an **unofficial** compatibility fork of
[Gabriela-Orzechowska/Blender-MKW-Utilities](https://github.com/Gabriela-Orzechowska/Blender-MKW-Utilities)
updated to run on **Blender 4.0 through 5.x** while remaining compatible with 3.x.

The original add-on is by **Gabriela_**. All credit for the tool itself goes to
the original author; this fork only contains compatibility fixes. Please report
issues with this fork here, not on the upstream repository.

Upstream baseline: `main` @ `6dc8adf`.

The in-app update check and the Download / Report a bug buttons point at this
fork. To retarget them, edit `GITHUB_REPO` near the top of `__init__.py`.

---

## Installation

Download **`MKW-Utilities-<version>.zip`** from
[Releases](https://github.com/Le-Sponk/Blender-MKW-Utilities/releases). The same
file works on every supported Blender version.

**Blender 4.2 and newer** - drag the ZIP into the Blender window, or
`Edit > Preferences > Get Extensions > dropdown > Install from Disk...`

**Blender 3.1 - 4.1** - `Edit > Preferences > Add-ons > Install...`

Install the **ZIP**, not a bare `__init__.py`.

### Optional: Wiimms SZS Tools

KCL import/export requires [Wiimms SZS Tools](https://szs.wiimm.de/) (`wszst`,
`wkclt`). The add-on searches `PATH` and the standard install locations. If it
cannot find them, set the folder in
`Preferences > Add-ons > Mario Kart Wii Utilities > Wiimms SZS Tools folder`
and press **Re-check for WSZST**.

Minimap BRRES export additionally requires [ABMatt](https://github.com/Robert-N7/abmatt).

### Collada (.dae) export

`File > Export > Autodesk Collada (.dae)` has two methods:

- **Autodesk FbxConverter** (default) - exports FBX and converts it with the
  bundled converter. This is the original behaviour and is used automatically
  when the converter is present, which in practice means Windows.
- **Built-in** - writes the Collada file directly, with no external tools.
  Used automatically when the converter is unavailable, so DAE export works on
  Linux and macOS, and on Blender 5.x where Blender's own Collada exporter was
  removed.

Geometry is written as `<triangles>`, one group per material, which is what
ABMatt and BrawlCrate expect. A model with several materials produces several
MDL0 materials rather than one.

**Copy Textures** (built-in method) writes each material's image texture next
to the `.dae`, under the filename the Collada file references, so BrawlCrate
resolves them on import. This replaces the *Texture Options > Copy* setting
from Blender's old Collada exporter.

Textures are found by following a material's node tree to the image feeding
Base Color, falling back to any image texture node. Packed and generated
images are written out too.

### Blender's `.001` suffixes

Blender appends `.001`, `.002` and so on whenever a name is already taken.
This shows up in two places:

- **Trailing**, on a datablock name: `d64_road.png.001`
- **Interior**, in a filename on disk: `d64_road.png.001.png` - written when a
  texture is saved or copied through Blender while the target name exists

Either form carried into an export produces a broken texture in BrawlCrate,
such as `d64_road.png.001`, which then shows the wrong texture in game. Both
forms are stripped.

Exports strip these suffixes automatically:

- Image datablocks that point at the same file on disk collapse into a single
  Collada `<image>` and a single copied texture.
- A texture is copied out under its cleaned name, so `d64_road.png.001.png`
  on disk is written and referenced as `d64_road.png`.
- Material, object and texture names are written without the suffix, in both
  the Collada and OBJ exporters.

Your .blend file is not modified. If two genuinely different files share a
name once the suffix is removed, they are kept apart and the export reports
which one was renamed.

---

## Changes in this fork

### Blender 4.x / 5.x compatibility

1. **Registration was gated on a hard-coded folder name.** `register()` only ran
   its body if the install directory was named `Blender-KMP-Utilities`. Any other
   name (including the one Blender 4.2+ generates for extensions) meant the
   add-on reported itself as enabled while registering nothing at all: no
   operators, no `Scene.kmpt`, panels with no data behind them.

   | | operators registered | `Scene.kmpt` |
   |---|---|---|
   | before | 0 | absent |
   | after | 8 | present |

2. **`Mesh.calc_normals_split()` was removed in Blender 4.1.** It was called
   unconditionally, so OBJ export with normals raised `AttributeError` on 4.1+.

3. **Principled BSDF sockets were addressed by index.** `inputs[4]`-`inputs[7]`
   were used for Specular and Metallic. Those indices moved in 4.0 and again in
   5.0, where index 5 is `Normal`, a vector socket. Sockets are now resolved by
   name, with `Specular` mapped to `Specular IOR Level` on 4.0+.

4. **`unregister()` failed on partial registration** with
   `missing bl_rna attribute`, leaving handlers and menu items behind.

5. **Private API import.** `bpy_extras.io_utils._check_axis_conversion` replaced
   with a local helper built on the public `axis_conversion_ensure`.

6. **Deprecated node-menu modules** (`nodeitems_utils`, `nodeitems_builtins`)
   are now imported defensively so their eventual removal cannot break loading.

7. **Blocking network I/O on every file load.** The update check made three
   un-timeouted GitHub API calls with no error handling, so opening any `.blend`
   offline produced a traceback. Now guarded, given a timeout, and skipped
   entirely when disabled in preferences.

8. **`os.popen` at register time** replaced with `subprocess.run` plus a timeout.

9. **`SyntaxWarning: invalid escape sequence`** in a property description.

10. **Added `blender_manifest.toml`** so the add-on installs as a native
    Blender 4.2+ extension.

### Wiimms SZS Tools / ABMatt integration

11. **`lower-walls.txt` was missing from the repository.** The KCL exporter's
    default "un-bean corner" mode is `LOWER`, which passes
    `--kcl-script=<plugin dir>/lower-walls.txt` to `wkclt`. That file was
    deleted from git but is still present in the release ZIP, so building from
    source produced an exporter whose default path always failed. Recovered
    from history and added to the build.

12. **The KCL script path used a hard-coded Windows backslash**, so it was
    broken on Linux and macOS even when the file was present.

13. **Minimap / BRRES export was Windows-only.** It split paths on a literal
    `\` and required the bundled `FbxConverter.exe` to turn FBX into COLLADA.
    ABMatt also accepts OBJ, and Blender's OBJ exporter is available on every
    platform and version (Collada export was removed in Blender 5.0), so OBJ is
    now used when the converter is unavailable.

14. **Minimap export crashed on meshes without a material.** ABMatt fails with
    `AttributeError: 'NoneType' object has no attribute 'encode'`. Now
    pre-checked, naming the offending objects.

15. **`os.system` / `os.popen`** replaced with `subprocess.run` argument lists
    for the ABMatt and FbxConverter calls.

### Tool discovery

16. **"Please download Wiimms SZS Tools" shown when WSZST was installed.**
    Two separate defects:

    *PATH.* Detection ran `subprocess.run(["wszst", ...])`, which only searches
    `PATH`. Blender launched from a desktop icon, Start menu or Dock does not
    inherit the login shell's `PATH`, so an install in `/usr/local/bin` or
    `%ProgramFiles%\Wiimm\SZS` was invisible.

    *Caching.* The result was stored in a module global set once during
    `register()` and never re-evaluated, so installing the tools afterwards had
    no effect. "Reload Scripts" re-runs `register()` in the same process with
    the same environment, which is why restarting did not help either.

    Search order is now: the folder set in preferences, then `PATH`, then the
    standard install locations. Added a **Wiimms SZS Tools folder** preference
    with a status readout and a **Re-check for WSZST** button. All `wkclt` and
    `abmatt` calls use the resolved absolute path.

17. **Sandboxed Blender (Flatpak / Snap).** A confined Blender cannot see the
    host's `/usr/local` at all, so the folder appears not to exist in the file
    browser. The add-on now also searches the host mount points
    (`/run/host/...`, `/var/lib/snapd/hostfs/...`), falls back to
    `flatpak-spawn --host`, and reports the specific fix in the KCL panel
    instead of repeating the generic download message.

### Other fixes

18. **`KeyError` on Import KCL.** `merge_duplicate_flags()` stored the active
    object by name, then stripped a `.001` suffix. When the base name was
    already taken Blender silently re-appended the suffix, so the rename never
    happened, and the object was then merged away by the join loop:

    ```
    KeyError: bpy_prop_collection[key]: key "ROAD_00_F0000.001" not found
    ```

    Only `ReferenceError` was caught. The object is now tracked by reference,
    the suffix is stripped only when the base name is free, and selection falls
    back to a surviving object.

19. **KCL export gave no feedback about skipped objects.** See below.

---

## Troubleshooting

### Exported KCL appears as a small plane in KMP Editor

Objects are only exported if their name ends in a valid KCL flag. The exporter
defaults to *"Only objects with KCL Flag"*, and anything without one is dropped,
so a course can collapse to whatever few objects happened to be named correctly.

The suffix must be `_F` followed by exactly 4 hex digits:

| Name | Result |
|---|---|
| `road_F0000` | exported |
| `ROAD_00_F0000` | exported |
| `wall_F000C` | exported |
| `ROAD_00_F0000.001` | exported (duplicate suffix is handled) |
| `Road_segment_0` | skipped |
| `Plane`, `Cube.001` | skipped |
| `road_f0000` | skipped, the `F` must be uppercase |
| `road_F0`, `road_F00000` | skipped, must be exactly 4 hex digits |

This fork reports what it exported. Check the status bar and system console:

```
[MKW Utilities] KCL export: 9 object(s), 148 triangle(s)
[MKW Utilities] KCL extent (game units): X=41000.0 Y=2200.0 Z=39000.0  (scale=100)
[MKW Utilities] SKIPPED (no valid KCL flag in name): Road_segment_0, ...
```

An extent of a few hundred units means only a small object was exported.

To verify a KCL outside Blender:

```
wkclt analyze course.kcl     # triangle count and coordinate bounds
wkclt flags   course.kcl     # per-flag triangle breakdown
python3 kcl_parse.py course.kcl
```

### "Please download Wiimms SZS Tools" when they are installed

Press **Re-check for WSZST**, or set the folder explicitly in
`Preferences > Add-ons > Mario Kart Wii Utilities`.

If browsing to `/usr/local` from Blender's file picker shows no `local` folder
at all, Blender is sandboxed. Check with:

```
ls /.flatpak-info        # exists: Flatpak
echo $SNAP_NAME          # non-empty: Snap
```

**Flatpak** mounts the host's `/usr` at `/run/host/usr`; `/usr/local` is not
exposed by default. Grant access, restart Blender, then press Re-check:

```
flatpak override --user --filesystem=host org.blender.Blender
```

**Snap** confinement cannot execute host binaries and cannot be relaxed with a
flag. Install Blender from [blender.org](https://www.blender.org/download/) or
via the system package manager instead.

Run `diagnose.py` (Scripting tab > Open > Run Script) to report packaging,
`PATH`, filesystem visibility and tool lookup in one go.

### BrawlCrate: "Unable to find an entry point named 'glActiveTexture'"

Something I ran into in testing Windows, and not a model or add-on problem.
`glActiveTexture` is OpenGL 1.3; Windows'
`opengl32.dll` only exports OpenGL 1.1 and everything newer comes from a GPU
driver. Without one, Windows falls back to the "GDI Generic" software renderer
and the function does not exist. This is common in virtual machines.

The stack trace is entirely in the paint path, and `MDL0ObjectNode` already
exists at that point, so the model parsed correctly and only the 3D preview
failed. The imported model can usually still be saved.

Fixes:

1. Enable 3D acceleration for the VM and install guest additions/tools.
2. Install [Mesa3D llvmpipe](https://github.com/pal1000/mesa-dist-win), a
   software OpenGL 4.5 implementation. Prefer the **system-wide** deployment
   tool: it registers under `OpenGLDrivers\MSOGL` and is used whenever no
   hardware driver is present, which avoids both the DLL search order and the
   32/64-bit mismatch (BrawlCrate is 32-bit only).
3. Run BrawlCrate on the host instead of in the VM.

---

## Development

```
python3 build.py                 # produce the ZIP into dist/
```

Test scripts run against a real Blender binary:

```
blender -b --factory-startup --python verify.py       -- <addon-dir>
blender -b --factory-startup --python wszst_test.py   -- <addon-dir>
blender -b --factory-startup --python detect_test.py  -- <addon-dir>
blender -b --factory-startup --python sandbox_test.py -- <addon-dir> hostpath
blender -b --factory-startup --python roundtrip_test.py -- <addon-dir>
```

`kcl_parse.py` is a standalone strict KCL parser used to validate exported
files independently of Wiimms' tools.

Verified against Blender 4.0.2, 4.1.1, 4.2.9 LTS, 4.5.9 LTS and 5.2.1 LTS,
with Wiimms SZS Tools v2.42a and ABMatt v1.3.2.

---

## Licence

GPL-2.0-or-later, matching the licence declared in the upstream source. The
full text is in `LICENSE`; see `NOTICE.md` for how that was determined and for
third-party components.

## Privacy

The update check is **disabled by default**. When enabled in
`Preferences > Add-ons > Mario Kart Wii Utilities`, it contacts the GitHub API
on file load to compare release tags. Nothing else is sent, and failures are
ignored rather than interrupting the file load.
