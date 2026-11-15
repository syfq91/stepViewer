"""Print post counts and bounds for a STEP file.

    python scripts/inspect_step.py model.step
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2

    from stepviewer.cad.loader import load_mesh

    for argument in argv[1:]:
        path = Path(argument)
        started = time.perf_counter()
        mesh = load_mesh(path)
        elapsed = time.perf_counter() - started
        low, high = mesh.bounds
        size = high - low
        print(f"{path.name}")
        print(f"  vertices  {mesh.vertex_count:,}")
        print(f"  triangles {mesh.triangle_count:,}")
        print(
            "  size      "
            f"{size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f} mm"
        )
        print(
            "  bounds    "
            f"[{low[0]:.1f}, {low[1]:.1f}, {low[2]:.1f}] .. "
            f"[{high[0]:.1f}, {high[1]:.1f}, {high[2]:.1f}]"
        )
        print(f"  loaded in {elapsed:.2f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
