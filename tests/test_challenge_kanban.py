"""Reto 3 (docs/challenges_to_test.md): tablero Kanban, probado como un usuario.

Un tablero pequeño en un JSON temporal (KANBAN_FILE): títulos únicos para encontrar
las tarjetas por su nombre, y así también se prueba que se carga y se guarda.
"""
import json
from pathlib import Path

import pytest

from fluxui.inspect import mount

KANBAN = Path(__file__).parent.parent / "examples" / "challenges" / "kanban"


def tarjeta(ident, titulo, **campos):
    return {"id": ident, "titulo": titulo, "descripcion": "", "etiquetas": [], "responsable": "", "fecha": "", **campos}


DATOS = {"columnas": [
    {"id": "c1", "nombre": "Pendiente", "tarjetas": [
        tarjeta("t1", "Alfa", etiquetas=["error"], responsable="Ana"), tarjeta("t2", "Beta", descripcion="Con texto"),
        tarjeta("t3", "Gamma", etiquetas=["mejora"]), tarjeta("t4", "Delta", responsable="Luis"),
    ]},
    {"id": "c2", "nombre": "En curso", "tarjetas": [tarjeta("t5", "Épsilon"), tarjeta("t6", "Zeta")]},
    {"id": "c3", "nombre": "Hecho", "tarjetas": []},
]}  # fmt: skip


@pytest.fixture
def archivo(tmp_path, monkeypatch):
    f = tmp_path / "tablero.json"
    f.write_text(json.dumps(DATOS, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("KANBAN_FILE", str(f))
    monkeypatch.delenv("KANBAN_DEMO", raising=False)
    return f


@pytest.fixture
def app(archivo):
    with mount(KANBAN / "src" / "App.flux") as app:
        yield app


def tablero(app):
    """{columna: [títulos]}, en orden."""
    return {c["nombre"]: [t["titulo"] for t in c["tarjetas"]] for c in app.get("tablero").columnas.peek()}


def card(app, titulo):
    return app.find("Tarjeta", label=titulo)


def columna(app, nombre):
    return app.find("Columna", label=nombre)


INICIAL = {"Pendiente": ["Alfa", "Beta", "Gamma", "Delta"], "En curso": ["Épsilon", "Zeta"], "Hecho": []}


def test_loads_the_json_board(app):
    assert tablero(app) == INICIAL
    assert len(app.find_all("Tarjeta")) == 6


def test_drag_between_columns_and_within_one(app):
    card(app, "Beta").drag_to(columna(app, "Hecho"))  # al hueco de la columna: al final
    assert tablero(app)["Hecho"] == ["Beta"] and "Beta" not in tablero(app)["Pendiente"]
    card(app, "Alfa").drag_to(card(app, "Épsilon"))  # sobre una tarjeta: delante de ella
    assert tablero(app)["En curso"] == ["Alfa", "Épsilon", "Zeta"]
    card(app, "Delta").drag_to(card(app, "Gamma"))  # sube en su columna: delante
    assert tablero(app)["Pendiente"] == ["Delta", "Gamma"]
    card(app, "Alfa").drag_to(card(app, "Zeta"))  # baja en su columna: detrás
    assert tablero(app)["En curso"] == ["Épsilon", "Zeta", "Alfa"]
    card(app, "Zeta").drag_to(columna(app, "Hecho"), cancel=True)  # Escape: nada
    assert tablero(app)["En curso"] == ["Épsilon", "Zeta", "Alfa"]
    assert len(app.find_all("Tarjeta")) == 6


def test_drag_a_column_header_reorders_columns(app):
    app.find("Text", text="Hecho").drag_to(columna(app, "Pendiente"))
    assert list(tablero(app)) == ["Hecho", "Pendiente", "En curso"]
    app.key("Ctrl+Z")
    assert list(tablero(app)) == ["Pendiente", "En curso", "Hecho"]


def test_context_menu_and_its_keyboard_alternatives(app):
    card(app, "Gamma").right_click()
    menu = app.find("MenuContextual")
    opciones = [o.label for o in app.find_all("flex") if o.label and (o.label.startswith("Mover a") or o.label in ("Abrir", "Duplicar", "Borrar"))]
    assert opciones == ["Mover a «En curso»", "Mover a «Hecho»", "Abrir", "Duplicar", "Borrar"]
    assert menu.visible
    app.find("flex", label="Mover a «Hecho»").click()
    assert tablero(app)["Hecho"] == ["Gamma"]
    assert not app.find_all("MenuContextual")
    # Lo mismo con el teclado, sin menú:
    card(app, "Gamma").key("Alt+Left")  # a la columna anterior
    assert tablero(app)["En curso"][0] == "Gamma"
    focused = app.window.activeFocusItem()
    assert focused is card(app, "Gamma").item  # es otra fila, pero recupera el foco
    card(app, "Gamma").key("Alt+Down")  # baja una posición
    assert tablero(app)["En curso"] == ["Épsilon", "Gamma", "Zeta"]
    card(app, "Gamma").key("Ctrl+D")  # duplicar
    assert tablero(app)["En curso"] == ["Épsilon", "Gamma", "Gamma", "Zeta"]
    card(app, "Alfa").key("Delete")  # borrar
    assert "Alfa" not in tablero(app)["Pendiente"]
    card(app, "Beta").key("Enter")  # abrir
    assert app.find("Detalle").visible
    card(app, "Beta").key("Shift+F10")  # el propio menú, con el teclado
    assert app.find("MenuContextual").visible
    app.key("Escape")
    assert not app.find_all("MenuContextual")
    assert app.window.activeFocusItem() is card(app, "Beta").item  # el foco vuelve a la tarjeta


def test_every_action_undoes_and_redoes(app):
    tab = app.get("tablero")
    card(app, "Alfa").drag_to(columna(app, "Hecho"))
    card(app, "Beta").key("Ctrl+D")
    card(app, "Delta").key("Delete")
    tab.renombrar("c2", "Haciendo")
    tab.nueva_columna("Bloqueado")
    tab.editar("t5", titulo="Épsilon 2", etiquetas=["docs"])
    tab.mover_columna("c3", 0)
    final = tablero(app)
    for _ in range(7):
        app.key("Ctrl+Z")
    assert tablero(app) == INICIAL
    assert app.get("tablero").tarjeta("t5")["etiquetas"] == []
    assert not app.find("Button", text="Deshacer").enabled
    for _ in range(7):
        app.key("Ctrl+Y")
    assert tablero(app) == final
    assert not app.find("Button", text="Rehacer").enabled


def test_detail_panel_edits_as_one_undoable_change(app):
    card(app, "Beta").double_click()
    app.find("TextField", label="Título").type("Beta revisada")
    app.find("Select", label="Responsable").choose("Marta")
    app.find("Checkbox", text="urgente").check()
    app.find("Button", text="Guardar").click()
    assert not app.find_all("Detalle")
    t = app.get("tablero").tarjeta("t2")
    assert (t["titulo"], t["responsable"], list(t["etiquetas"])) == ("Beta revisada", "Marta", ["urgente"])
    assert app.find("Tarjeta", label="Beta revisada").visible
    app.key("Ctrl+Z")
    t = app.get("tablero").tarjeta("t2")
    assert (t["titulo"], t["responsable"], list(t["etiquetas"])) == ("Beta", "", [])


def test_search_and_filters_dim_the_rest(app):
    def atenuadas():
        return sorted(c.label for c in app.find_all("Tarjeta") if c.item.property("opacity") < 0.5)

    assert atenuadas() == []
    app.find("TextField", label="Buscar").type("ta")  # Beta, Delta, Zeta
    app.wait(0.2)  # transición de opacidad
    assert atenuadas() == ["Alfa", "Gamma", "Épsilon"]
    app.find("Select", label="Filtrar por persona").choose("Luis")
    app.wait(0.2)
    assert atenuadas() == ["Alfa", "Beta", "Gamma", "Zeta", "Épsilon"]
    app.find("Button", text="Quitar filtros").click()
    app.wait(0.2)
    assert atenuadas() == []


def test_rename_and_add_columns(app):
    app.find("Text", text="En curso").double_click()
    app.find("TextField", label="Nombre de la columna").type("Haciendo").submit()
    assert list(tablero(app)) == ["Pendiente", "Haciendo", "Hecho"]
    app.find("Button", text="+ Columna").click()
    assert list(tablero(app))[-1] == "Nueva columna"
    app.find_all("flex", label="Añadir tarjeta")[0].click()  # la de la primera columna
    assert tablero(app)["Pendiente"][-1] == "Nueva tarjeta"


def test_changes_are_saved_to_the_json(app, archivo):
    card(app, "Alfa").drag_to(columna(app, "Hecho"))
    app.wait(until=lambda: "Hecho" in archivo.read_text(encoding="utf-8")
             and json.loads(archivo.read_text(encoding="utf-8"))["columnas"][2]["tarjetas"], timeout=3)
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    assert [t["titulo"] for t in datos["columnas"][2]["tarjetas"]] == ["Alfa"]
    assert datos["columnas"][2]["tarjetas"][0]["etiquetas"] == ["error"]


def test_card_local_state_survives_moves_in_and_between_columns(app):
    app.find("flex", label="Ver descripción de Beta").click()
    assert app.find("Text", text="Con texto").visible
    card(app, "Beta").drag_to(card(app, "Alfa"))  # misma <List>: la fila se mueve
    assert tablero(app)["Pendiente"][:2] == ["Beta", "Alfa"]
    assert app.find_all("Text", text="Con texto")
    card(app, "Beta").drag_to(columna(app, "Hecho"))  # otra <List>: la tarjeta se traslada
    assert tablero(app)["Hecho"] == ["Beta"]
    app.wait(0.5)
    assert app.find("Text", text="Con texto").visible
    app.key("Ctrl+Z")  # deshacer también la traslada de vuelta
    app.wait(0.5)
    assert tablero(app)["Pendiente"][:2] == ["Beta", "Alfa"]
    assert app.find("flex", label="Ocultar descripción de Beta")


def test_keyboard_move_to_another_column_keeps_focus_and_state(app):
    app.find("flex", label="Ver descripción de Beta").click()
    card(app, "Beta").key("Alt+Right")
    app.wait(0.5)
    assert tablero(app)["En curso"][0] == "Beta"
    assert app.find("flex", label="Ocultar descripción de Beta")
    app.key("Alt+Right")  # sin volver a enfocarla: la tarjeta trasladada conserva el foco
    app.wait(0.5)
    assert tablero(app)["Hecho"] == ["Beta"]


def test_dragging_to_the_edge_reaches_columns_out_of_view(monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest

    monkeypatch.setenv("KANBAN_DEMO", "10x5")
    with mount(KANBAN / "src" / "App.flux") as app:
        tab = app.get("tablero")
        cols = tab.columnas.peek()
        ident = cols[0]["tarjetas"][0]["id"]
        src = app.find_all("Tarjeta", label=cols[0]["tarjetas"][0]["titulo"])[0]
        start = src._center()
        edge = QPoint(app.window.width() - 15, start.y() + 150)
        QTest.mousePress(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, start)
        QTest.mouseMove(app.window, start + QPoint(30, 0))
        QTest.mouseMove(app.window, edge)
        app.wait(3)  # el tablero se desplaza hasta el final (~750 px/s a 15 px del borde)
        QTest.mouseRelease(app.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, edge)
        app.process()
        col, _ = tab.donde(ident)
        assert col["id"] == cols[-1]["id"]  # la última columna, que al empezar no se veía
