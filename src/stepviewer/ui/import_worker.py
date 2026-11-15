"""Tessellate imported STEP files on a worker thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal

from ..cad.loader import load_mesh_with_sha1


class ImportSignals(QObject):
    loaded = Signal(str, object, str)  # path, MeshData, sha1
    failed = Signal(str, str)  # path, message
    finished = Signal()


class ImportTask(QRunnable):
    def __init__(self, path: str, signals: ImportSignals) -> None:
        super().__init__()
        self._path = path
        self._signals = signals
        self.setAutoDelete(True)

    def run(self) -> None:
        try:
            mesh, sha1 = load_mesh_with_sha1(self._path)
        except Exception as exc:
            self._signals.failed.emit(self._path, str(exc) or exc.__class__.__name__)
        else:
            self._signals.loaded.emit(self._path, mesh, sha1)
        finally:
            self._signals.finished.emit()
