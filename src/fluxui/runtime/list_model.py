"""Modelo Qt de una región dinámica: una lista de puentes, uno por fila.

QML lo consume con un `Repeater`; dentro del delegado, el rol `fx` es el
puente de esa fila. Insertar, mover y eliminar filas emite las señales de
modelo correspondientes, así que Qt crea, reubica o destruye solo los
delegados afectados: las filas que se mueven conservan su estado visual.
"""
from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QObject, Property, Qt, Signal

from ..compiler.qml_generator import BRIDGE_NAME


class SlotModel(QAbstractListModel):
    BRIDGE_ROLE = Qt.ItemDataRole.UserRole + 1

    def __init__(self, delegate: QObject | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._rows: list[QObject] = []
        self._delegate = delegate
        # Filas que se están animando al salir: siguen en el modelo (Qt las muestra)
        # pero ya no cuentan para las posiciones que usan las regiones.
        self._leaving: set[int] = set()
        self._order = 0

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

    # Cambia con cada movimiento: el contenedor <flex> vuelve a colocar a sus hijos.
    orderChanged = Signal()

    def _get_order(self) -> int:
        return self._order

    order = Property(int, _get_order, notify=orderChanged)

    def _moved(self) -> None:
        self._order += 1
        self.orderChanged.emit()

    # -- operaciones (posiciones lógicas: sin las filas que están saliendo) ---------
    def __len__(self) -> int:
        return len(self._rows) - len(self._leaving)

    def _physical(self, pos: int) -> int:
        if not self._leaving:
            return pos
        seen = 0
        for i, row in enumerate(self._rows):
            if id(row) in self._leaving:
                continue
            if seen == pos:
                return i
            seen += 1
        return len(self._rows)

    @property
    def bridges(self) -> list[QObject]:
        return list(self._rows)

    def insert(self, position: int, bridge: QObject) -> None:
        position = self._physical(position)
        self.beginInsertRows(QModelIndex(), position, position)
        self._rows.insert(position, bridge)
        self.endInsertRows()

    def insert_many(self, position: int, entries: list) -> None:
        """Inserta varias filas seguidas con una sola notificación a Qt."""
        if not entries:
            return
        position = self._physical(position)
        self.beginInsertRows(QModelIndex(), position, position + len(entries) - 1)
        self._rows[position:position] = entries
        self.endInsertRows()

    def remove(self, position: int) -> QObject:
        return self._remove_physical(self._physical(position))

    def _remove_physical(self, position: int) -> QObject:
        self.beginRemoveRows(QModelIndex(), position, position)
        bridge = self._rows.pop(position)
        self.endRemoveRows()
        return bridge

    def start_leaving(self, position: int) -> QObject:
        """La fila deja de contar, pero sigue en el modelo hasta `finish_leaving` (su animación de salida)."""
        bridge = self._rows[self._physical(position)]
        self._leaving.add(id(bridge))
        return bridge

    def finish_leaving(self, bridge: QObject) -> None:
        self._leaving.discard(id(bridge))
        for i, row in enumerate(self._rows):
            if row is bridge:
                self._remove_physical(i)
                return

    def move(self, source: int, target: int) -> None:
        """Mueve la fila `source` para que quede en la posición final `target` (posiciones lógicas)."""
        if source == target:
            return
        if not self._leaving:  # caso habitual: posiciones lógicas = físicas
            destination = target + 1 if target > source else target
            if not self.beginMoveRows(QModelIndex(), source, source, QModelIndex(), destination):
                raise ValueError(f"movimiento de fila no válido: {source} -> {target}")
            self._rows.insert(target, self._rows.pop(source))
            self.endMoveRows()
            self._moved()
            return
        src = self._physical(source)
        row = self._rows[src]
        rest = self._rows[:src] + self._rows[src + 1:]
        # Posición física final: delante de la fila lógica `target` de la lista sin la que se mueve.
        seen, final = 0, len(rest)
        for i, other in enumerate(rest):
            if id(other) in self._leaving:
                continue
            if seen == target:
                final = i
                break
            seen += 1
        if final == src:
            return
        # beginMoveRows espera el índice *antes* del cual se inserta, en la lista previa.
        destination = final + 1 if final > src else final
        if not self.beginMoveRows(QModelIndex(), src, src, QModelIndex(), destination):
            raise ValueError(f"movimiento de fila no válido: {source} -> {target}")
        self._rows = rest[:final] + [row] + rest[final:]
        self.endMoveRows()
        self._moved()


class LazySlotModel(SlotModel):
    """Modelo de una lista virtualizada (`<List>`).

    Cada fila empieza como un *hueco* (cualquier objeto que no es un QObject)
    y su puente se crea con `factory(hueco)` la primera vez que Qt lo pide, es
    decir, cuando la fila se hace visible. Como el hueco viaja con la fila al
    insertar o mover, la creación es correcta aunque Qt pida datos en medio de
    una operación.
    """

    def __init__(self, factory, delegate: QObject | None = None, parent: QObject | None = None):
        super().__init__(delegate, parent)
        self._factory = factory  # (hueco) -> puente

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        row = index.row()
        if role != self.BRIDGE_ROLE or not 0 <= row < len(self._rows):
            return None
        entry = self._rows[row]
        if not isinstance(entry, QObject):
            entry = self._factory(entry)
            if entry is None:
                return None
            self._rows[row] = entry
        return entry

    def materialized(self) -> int:
        """Filas cuyo puente ya existe (para pruebas y mediciones)."""
        return sum(isinstance(r, QObject) for r in self._rows)

    def reset(self, entries: list) -> None:
        """Sustituye todas las filas de una vez (puentes o huecos): para cambios masivos."""
        self.beginResetModel()
        self._rows = list(entries)
        self.endResetModel()
