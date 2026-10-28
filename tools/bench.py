"""Medición indicativa del rendimiento de listas `{#each}` (Qt offscreen).

Uso:  python tools/bench.py [N ...]      (por defecto: 100 1000)

Cada fila tiene una casilla, un texto y un botón, como en la app de tareas.
Los tiempos incluyen la actualización de Python y la creación/movimiento de
los elementos Qt Quick (con `processEvents`), no el pintado en pantalla.
"""
from __future__ import annotations

import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QMetaObject  # noqa: E402

from janelkit.compiler import compile_source  # noqa: E402
from janelkit.qt_backend.application import Application  # noqa: E402

ROW = """
  {#each todos as todo (todo["id"])}
    <Row>
      <Checkbox checked={todo["done"]} on:change={todo["done"] = event}>{todo["title"]}</Checkbox>
      <Button on:click={todos.remove(todo)}>x</Button>
    </Row>
  {/each}
"""
HEAD = "<script>\nfrom janelkit import state\ntodos = state([])\n</script>\n"
APPS = {
    "Scroll": HEAD + "<Scroll>" + ROW + "</Scroll>",  # todas las filas existen
    "List": HEAD + "<Window width={400} height={600}><List>" + ROW + "</List></Window>",  # virtualizada
}


def measure(app: Application, n: int, kind: str = "Scroll") -> dict[str, float]:
    mounted = app.mount(compile_source(APPS[kind], "Bench.janel"))
    todos = mounted.instance.namespace["todos"]

    def items(k: int, start: int = 0) -> list[dict]:
        return [{"id": start + i, "title": f"Tarea {start + i}", "done": False} for i in range(k)]

    results: dict[str, float] = {}

    views = [i for i in _items(mounted.root) if i.inherits("QQuickListView")]

    def timed(label: str, fn) -> None:
        t0 = time.perf_counter()
        fn()
        for view in views:  # sin ventana visible, ListView no se dispone solo
            QMetaObject.invokeMethod(view, "forceLayout")
        app.qt_app.processEvents()
        results[label] = (time.perf_counter() - t0) * 1000

    timed("crear la lista completa", lambda: setattr(todos, "value", items(n)))
    timed("insertar una fila en medio (reasignando)", lambda: setattr(
        todos, "value", [*todos.value[: n // 2], *items(1, 10**6), *todos.value[n // 2:]]
    ))
    timed("insertar una fila en medio (insert)", lambda: todos.value.insert(n // 2, items(1, 2 * 10**6)[0]))
    timed("añadir al final (append)", lambda: todos.value.append(items(1, 3 * 10**6)[0]))
    timed("editar una fila (reasignando)", lambda: setattr(
        todos, "value", [{**t, "done": True} if t["id"] == n // 3 else t for t in todos.value]
    ))
    timed("editar una fila (en el sitio)", lambda: todos.value[n // 4].__setitem__("done", True))
    timed("invertir el orden", lambda: todos.value.reverse())
    timed("vaciar", lambda: todos.value.clear())
    app.unmount(mounted)
    return results


def _items(root):
    start = root.contentItem() if hasattr(root, "contentItem") else root
    stack = [start]
    while stack:
        item = stack.pop()
        yield item
        stack.extend(item.childItems())


def main() -> int:
    sizes = [int(a) for a in sys.argv[1:]] or [100, 1000]
    app = Application([])
    for kind, kind_sizes in (("Scroll", sizes), ("List", sorted({*sizes, 10_000}))):
        measure(app, 50, kind)  # calentamiento: compilación de QML y clases puente
        table = {n: measure(app, n, kind) for n in kind_sizes}
        labels = list(next(iter(table.values())))
        print(f"\n<{kind}>\n")
        print("| Operación | " + " | ".join(f"{n} filas" for n in kind_sizes) + " |")
        print("|---|" + "---|" * len(kind_sizes))
        for label in labels:
            print(f"| {label} | " + " | ".join(f"{table[n][label]:.0f} ms" for n in kind_sizes) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
