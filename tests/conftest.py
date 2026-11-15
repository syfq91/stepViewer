import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    if not (FIXTURES / "table.step").is_file():
        pytest.skip("run 'python scripts/make_fixtures.py' to create the STEP fixtures")
    return FIXTURES


@pytest.fixture(scope="session")
def table_step(fixtures_dir: Path) -> Path:
    return fixtures_dir / "table.step"


@pytest.fixture(scope="session")
def chair_step(fixtures_dir: Path) -> Path:
    return fixtures_dir / "chair.step"


@pytest.fixture
def box_mesh():
    """A 1000 x 600 x 750 box mesh anchored at the origin."""
    import numpy as np

    from stepviewer.cad.mesh import MeshData

    sx, sy, sz = 1000.0, 600.0, 750.0
    vertices = np.array(
        [
            [0, 0, 0],
            [sx, 0, 0],
            [sx, sy, 0],
            [0, sy, 0],
            [0, 0, sz],
            [sx, 0, sz],
            [sx, sy, sz],
            [0, sy, sz],
        ],
        dtype=np.float32,
    )
    faces = np.array(
        [
            [0, 1, 2],
            [0, 2, 3],
            [4, 5, 6],
            [4, 6, 7],
            [0, 1, 5],
            [0, 5, 4],
            [1, 2, 6],
            [1, 6, 5],
            [2, 3, 7],
            [2, 7, 6],
            [3, 0, 4],
            [3, 4, 7],
        ],
        dtype=np.int32,
    )
    return MeshData.create(vertices, faces)
