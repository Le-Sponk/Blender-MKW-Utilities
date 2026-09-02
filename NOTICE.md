# Licensing notice

This project is an unofficial fork of
[Gabriela-Orzechowska/Blender-MKW-Utilities](https://github.com/Gabriela-Orzechowska/Blender-MKW-Utilities),
originally written by **Gabriela_**.

## Licence basis

The upstream repository does not contain a `LICENSE` file. The licence is
declared in-source: `export_obj.py` carries

    # SPDX-License-Identifier: GPL-2.0-or-later

`export_obj.py` is derived from Blender's own `io_scene_obj` exporter, which is
GPL-2.0-or-later. Because that code is incorporated into this add-on, the work
as a whole is distributed under **GPL-2.0-or-later**, and the full licence text
is included in `LICENSE`.

This fork adds the `LICENSE` file that upstream omits. It does not change the
licence, and it is not a licensing decision made by this fork: it records the
terms already declared in the source.

If the original author states different terms, those take precedence and this
file should be updated to match.

## Third-party components

- `export_obj.py` — derived from the Blender OBJ exporter, GPL-2.0-or-later.
- `lower-walls.txt` — a `wkclt` script by Wiimm (2015), recovered from upstream
  git history where it was removed but still shipped in release archives. It is
  part of the Wiimms SZS Tools ecosystem.

Wiimms SZS Tools and ABMatt are **not** bundled with this add-on. They are
external programs invoked when present, and each carries its own licence.
