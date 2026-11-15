"""Generate the STEP fixtures used by the tests and for manual smoke tests.

    python scripts/make_fixtures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

#: name -> (size_x, size_y, size_z) in millimetres
PARTS = {
    "chair": (450.0, 450.0, 900.0),
    "table": (1200.0, 800.0, 750.0),
    "room_shell": (4000.0, 3000.0, 2700.0),
}


def write_box(path: Path, sx: float, sy: float, sz: float) -> None:
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.STEPControl import STEPControl_AsIs, STEPControl_Writer

    shape = BRepPrimAPI_MakeBox(sx, sy, sz).Shape()
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    if writer.Write(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"could not write {path}")


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for name, size in PARTS.items():
        path = FIXTURES / f"{name}.step"
        write_box(path, *size)
        print(f"{path}  ({size[0]:g} x {size[1]:g} x {size[2]:g} mm)")
    (FIXTURES / ".gitkeep").touch()
    return 0


if __name__ == "__main__":
    sys.exit(main())
