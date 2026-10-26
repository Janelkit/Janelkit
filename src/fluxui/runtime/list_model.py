"""Modelo Qt de una región dinámica: una lista de puentes, uno por fila.

QML lo consume con un `Repeater`; dentro del delegado, el rol `fx` es el
puente de esa fila. Insertar, mover y eliminar filas emite las señales de
modelo correspondientes, así que Qt crea, reubica o destruye solo los
delegados afectados: las filas que se mueven conservan su estado visual.
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, Property, Qt

from ..compiler.qml_generator import BRIDGE_NAME


class SlotModel(QAbstractListModel):
    BRIDGE_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, delegate: QObject | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._rows: list[QObject] = []
        self._delegate = delegate

    # -- QAbstractListModel ----------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if role == self.BRIDGE_ROLE and 0 <= index.row() < len(self._rows):
            return self._rows[index.row()]
        return None

    def roleNames(self) -> dict[int, QByteArray]:
        return {self.BRIDGE_ROLE: QByteArray(BRIDGE_NAME.encode())}

    def _get_delegate(self) -> QObject | None:
        return self._delegate

    # Componente QML que se repite cuando la región es un componente hijo.
    delegate = Property(QObject, _get_delegate, constant=True)

    # -- operaciones -----------------------------------------------------------
    def __len__(self) -> int:
        return len(self._rows)

    @property
    def bridges(self) -> list[QObject]:
        return list(self._rows)

    def insert(self, position: int, bridge: QObject) -> None:
        self.beginInsertRows(QModelIndex(), position, position)
        self._rows.insert(position, bridge)
        self.endInsertRows()

    def remove(self, position: int) -> QObject:
        self.beginRemoveRows(QModelIndex(), position, position)
        bridge = self._rows.pop(position)
        self.endRemoveRows()
        return bridge

    def move(self, source: int, target: int) -> None:
        """Mueve la fila `source` para que quede en la posición final `target`."""
        if source == target:
            return
        # beginMoveRows espera el índice *antes* del cual se inserta, en la lista previa.
        destination = target + 1 if target > source else target
        if not self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), destination):
            raise ValueError(f"movimiento de fila no válido: {source} -> {target}")
        self._rows.insert(target, self._rows.pop(source))
        self.endMoveRows()
