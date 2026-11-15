"""Tunable constants shared across the application."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "StepViewer"

PROJECT_FORMAT = "stepviewer-layout"
PROJECT_VERSION = 1
PROJECT_SUFFIX = ".svproj"

UNITS = "mm"

#: Chordal deflection used when tessellating a STEP file, in millimetres.
MESH_LINEAR_TOLERANCE = 0.5
#: Angular deflection used when tessellating a STEP file, in radians.
MESH_ANGULAR_TOLERANCE = 0.35

DEFAULT_GRID_SIZE = 100.0
DEFAULT_GRID_EXTENT = 20000.0
MIN_GRID_SIZE = 1.0
MAX_GRID_SIZE = 1000.0

#: Distance in world units within which an edge/centre alignment snaps.
SNAP_THRESHOLD = 80.0

#: Gap left between models when they are auto-placed on import.
AUTO_PLACE_GAP = 250.0

DEFAULT_ITEM_COLOR = "#9fb3c8"
SELECTION_COLOR = "#ff9f1c"
GUIDE_COLOR = "#e63946"
GRID_COLOR = "#3b4252"
GRID_AXIS_COLOR = "#4c566a"
BACKGROUND_COLOR = "#1b1f27"


def cache_dir() -> Path:
    """Directory holding tessellated meshes, created on demand."""
    root = os.environ.get("XDG_CACHE_HOME")
    base = Path(root) if root else Path.home() / ".cache"
    path = base / "stepviewer" / "meshes"
    path.mkdir(parents=True, exist_ok=True)
    return path
