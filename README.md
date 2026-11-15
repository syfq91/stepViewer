# StepViewer

Arrange CAD models of a house and its furniture on a floor plan, then export the
result as a single STEP file.

Models are imported as `.step` / `.stp` files. Nothing is converted by hand: the
app tessellates each source file once, caches the triangles on disk, and lets you
place as many copies as you like.

## Requirements

- Python 3.11 – 3.13
- Linux, macOS or Windows (64-bit). Linux wheels exist for CPython 3.11–3.14.

## Install

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
python -m stepviewer
# or, after install
stepviewer layout.svproj
```

## Workflow

1. **File → Import STEP…** and pick your house shell / walls first.
2. Select it in the scene tree and tick **Locked** so it cannot be dragged by
   accident.
3. Import furniture models. Each import is placed to the right of the existing
   layout, so nothing starts out overlapping.
4. Drag furniture around in the **Plan** view. Positions snap to a 100 mm grid
   and to the edges/centres of neighbouring items, with guide lines showing what
   you are lining up with.
5. **Tab** switches between the plan view and a 3D inspection view.
6. **File → Export STEP…** writes every item into one STEP file with its world
   placement baked in.

## Controls

| Action | Input |
| --- | --- |
| Select item | Left click |
| Move item | Left drag (plan view) |
| Rotate item freely | Right drag horizontally (plan view) |
| Rotate 90° | `R` / `Shift+R` |
| Pan view | Middle drag (plan view), middle drag (3D) |
| Zoom | Mouse wheel |
| Fit to layout | `F` |
| Toggle plan / 3D | `Tab` |
| Toggle grid snapping | `G` |
| Duplicate selection | `Ctrl+D` |
| Delete selection | `Delete` |
| Undo / redo | `Ctrl+Z` / `Ctrl+Shift+Z` |

## Files

- Layout projects are JSON documents with the `.svproj` suffix. They store a
  path to each source STEP file plus every item's position, rotation, scale and
  colour — not the geometry itself.
- The triangle cache lives in `~/.cache/stepviewer/meshes` and can be deleted at
  any time. It is keyed by the SHA-1 of the source file and the tessellation
  tolerance.

## Notes and troubleshooting

- **Units are millimetres.** OCCT converts STEP files that declare other units,
  and `cascadio` returns glTF, which is metre-based, so every model is scaled up
  on import. The layout is millimetres end to end.
- **Blank window on Wayland**: VTK's Qt widget sometimes needs the X11 backend.
  Start the app with `QT_QPA_PLATFORM=xcb python -m stepviewer`.
- **Slow import of large assemblies**: raise `MESH_LINEAR_TOLERANCE` in
  `src/stepviewer/config.py` (0.5 mm by default) to get fewer triangles faster.
  Imports run one file at a time on a worker thread so the window stays usable.
- `cascadio` uses PyPI space aggressively and older releases are removed; the
  pinned `0.1.1` is the intended version, with `0.0.13` as a fallback.
- Use `python scripts/inspect_step.py model.step` to check what the importer
  sees for a file (triangle counts, size, bounds) before blaming the layout.

## How it works

- STEP files are tessellated by `cascadio` (OpenCASCADE under the hood) into a
  glTF payload, which `trimesh` turns into vertices, triangles and per-part
  colours. The result is cached, so re-importing a file is instant.
- Rendering is VTK embedded in Qt: one renderer, one actor per placed item, and
  a per-item `vtkTransform` for the placement. Dragging only moves the actor;
  the document is updated once, on mouse release, as an undoable command.
- The plan view is an orthographic top-down camera, which makes screen movement
  map linearly onto the floor plane — no ray casting is involved.
- Export reads the original STEP files again and applies each item's transform
  to the real B-rep with OpenCASCADE, so the output keeps exact geometry.

## Known limitations

- Moving several items at once is not supported: drag moves one item, while
  delete, duplicate, rotate and nudge act on the whole selection.
- The exported STEP is a single compound of solids with world placements baked
  in. It has no per-item product names or assembly tree (that needs the
  `STEPCAFControl` writer).
- No wall drawing, room detection, collision warnings or dimension annotations.
- Only STEP/STP is imported; IGES, SAT and mesh formats are out of scope.

## Development

```bash
python scripts/make_fixtures.py   # generates simple STEP files for the tests
pytest -q                         # unit, panel and viewer tests
pytest -q -m slow                 # CAD round-trip tests (real OCCT work)
```

The test suite runs headless: Qt tests use the offscreen platform and the viewer
tests build VTK objects without rendering them.
