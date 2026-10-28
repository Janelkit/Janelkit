"""Reto 2 (docs/challenges_to_test.md): hoja de cálculo, probada como un usuario.

Una compra pequeña en un CSV temporal (HOJA_FILE), con fórmulas que dependen unas de
otras; la hoja sigue teniendo 10 000 × 26 celdas.
"""
from pathlib import Path

import pytest

from janelkit.inspect import mount
from janelkit_desktop import clipboard

HOJA = Path(__file__).resolve().parents[1] / "hoja"
CSV = (
    "Producto,Precio,Unidades,Total\n"
    "Pan,1.5,4,=B2*C2\n"
    "Leche,1,6,=B3*C3\n"
    "Huevos,2.25,2,=B4*C4\n"
    "Total,,,=SUMA(D2:D4)\n"
)


@pytest.fixture
def archivo(tmp_path, monkeypatch):
    f = tmp_path / "compra.csv"
    f.write_text(CSV, encoding="utf-8")
    monkeypatch.setenv("HOJA_FILE", str(f))
    monkeypatch.delenv("HOJA_DEMO", raising=False)
    return f


@pytest.fixture
def app(archivo):
    with mount(HOJA / "src" / "App.janel") as app:
        yield app


def rejilla(app):
    return app.find(label="Hoja")


def teclas(app, *combinaciones):
    for k in combinaciones:
        rejilla(app).key(k)


def editor(app):
    return app.find("TextField", label="Editar celda")


def escrito(app, celda):
    from services.formulas import referencia

    return app.get("hoja").escrito(*referencia(celda))


def texto(app, celda):
    from services.formulas import referencia

    return app.get("hoja").texto(*referencia(celda))


def test_opens_the_csv_and_computes_the_formulas(app):
    assert app.get("hoja").filas == 10_000
    assert [texto(app, c) for c in ("D2", "D3", "D4", "D5")] == ["6", "6", "4.5", "16.5"]
    assert "16.5" in app.texts()
    assert app.get("titulo") == "compra.csv — Hoja"


def test_typing_edits_in_place_and_dependents_update(app):
    teclas(app, "Down", "Right", "3")  # B2: empezar a escribir sustituye el contenido
    assert editor(app).text == "3"
    editor(app).key("Enter")  # confirma y baja
    assert app.get("vista").cursor.value == (2, 1)
    assert escrito(app, "B2") == "3"
    assert texto(app, "D2") == "12" and texto(app, "D5") == "22.5"
    assert "22.5" in app.texts()
    assert not app.find_all("TextField", label="Editar celda")
    assert app.get("titulo").startswith("• ")


def test_f2_edits_the_formula_and_escape_cancels(app):
    teclas(app, "Down", "End", "F2")  # D2
    assert editor(app).text == "=B2*C2"
    editor(app).type("=1")
    editor(app).key("Escape")
    assert escrito(app, "D2") == "=B2*C2"
    assert not app.find_all("TextField", label="Editar celda")
    teclas(app, "F2")
    editor(app).type("=B2*C2*2")
    editor(app).key("Tab")  # confirma y pasa a la derecha
    assert texto(app, "D2") == "12" and app.get("vista").cursor.value == (1, 4)


def test_formula_errors_and_cycles(app):
    hoja = app.get("hoja")
    hoja.escribir({(0, 5): "=F1+1", (1, 5): "=1/0", (2, 5): "=G3", (2, 6): "=F3", (3, 5): "=NADA(1)"}, "errores")
    assert [texto(app, c) for c in ("F1", "F2", "F3", "G3", "F4")] == ["#CICLO!", "#DIV/0!", "#CICLO!", "#CICLO!", "#NOMBRE?"]
    hoja.escribir({(2, 6): "7"}, "romper el ciclo")
    assert texto(app, "F3") == "7"


def test_shift_selects_copy_and_paste_tab_separated(app):
    teclas(app, "Down", "Shift+Down", "Shift+Right", "Ctrl+C")  # A2:B3
    assert app.get("vista").nombre_activa() == "B3 (A2:B3)"
    assert clipboard.paste() == "Pan\t1.5\nLeche\t1\n"
    teclas(app, "Ctrl+Home")
    for _ in range(8):
        teclas(app, "Down")
    teclas(app, "Ctrl+V")  # en A9
    assert [escrito(app, c) for c in ("A9", "B9", "A10", "B10")] == ["Pan", "1.5", "Leche", "1"]
    assert app.get("vista").rango.value == (8, 0, 9, 1)  # queda seleccionado lo pegado
    clipboard.copy("x\ty\tz\r\n1\t2\t3\r\n")  # como lo copia Excel
    teclas(app, "Escape", "Ctrl+V")
    assert [escrito(app, c) for c in ("A9", "C9", "C10")] == ["x", "z", "3"]


def test_cut_delete_undo_and_redo(app):
    teclas(app, "Down", "Right", "Shift+Down")  # B2:B3
    teclas(app, "Delete")
    assert texto(app, "D5") == "4.5"
    teclas(app, "Ctrl+Z")
    assert texto(app, "D5") == "16.5"
    teclas(app, "Ctrl+Y")
    assert texto(app, "D5") == "4.5"
    teclas(app, "Ctrl+Shift+Z", "Ctrl+Z")  # nada que rehacer; deshace el borrado
    assert texto(app, "D5") == "16.5"
    teclas(app, "Ctrl+X")
    assert clipboard.paste() == "1.5\n1\n" and escrito(app, "B2") == ""
    app.find("Button", text="Deshacer").click()
    assert escrito(app, "B2") == "1.5"
    assert app.find("Button", text="Rehacer").enabled


def test_sort_keeps_the_frozen_header_and_puts_empty_last(app):
    app.find("Checkbox", text="Congelar fila 1").check()
    teclas(app, "Down", "Right")  # columna B
    app.find("Button", text="Ordenar Z→A").click()
    hoja = app.get("hoja")
    assert [hoja.escrito(r, 0) for r in range(5)] == ["Producto", "Huevos", "Pan", "Leche", "Total"]
    teclas(app, "Ctrl+Z")
    assert [hoja.escrito(r, 0) for r in range(5)] == ["Producto", "Pan", "Leche", "Huevos", "Total"]


def test_columns_scroll_horizontally_and_column_a_can_be_frozen(app):
    vista = app.get("vista")
    caben = vista.caben.value
    assert 4 <= caben < 26 and vista.visibles.value == list(range(caben))
    for _ in range(caben + 2):
        teclas(app, "Right")
    assert vista.cursor.value == (0, caben + 2)
    assert vista.visibles.value[-1] == caben + 2  # la columna activa se ve
    app.find("Checkbox", text="Congelar columna A").check()
    assert vista.visibles.value[0] == 0 and vista.visibles.value[-1] == caben + 2
    teclas(app, "Home")
    assert vista.visibles.value[:2] == [0, 1]


def test_page_down_scrolls_the_list_to_the_active_row(app):
    teclas(app, "Ctrl+Down")  # al final de los datos: fila 5
    assert app.get("vista").cursor.value == (4, 0)
    for _ in range(30):
        teclas(app, "PageDown")
    r, _ = app.get("vista").cursor.value
    assert r > 300
    assert str(r + 1) in app.texts()  # el número de la fila activa está a la vista


def test_mouse_selects_and_double_click_edits(app):
    app.find("Text", text="Leche").press().release()
    assert app.get("vista").cursor.value == (2, 0)
    app.find("Text", text="Huevos").double_click()
    assert editor(app).text == "Huevos"
    editor(app).type("Huevos camperos")
    rejilla(app).focus()  # perder el foco confirma sin moverse
    assert escrito(app, "A4") == "Huevos camperos" and app.get("vista").cursor.value == (3, 0)


def test_formula_bar_shows_and_edits_the_active_cell(app):
    teclas(app, "Down", "End")
    barra = app.find("TextField", label="Contenido de la celda")
    assert barra.text == "=B2*C2"
    barra.type("=B2+C2").submit()
    assert texto(app, "D2") == "5.5"


def test_save_writes_the_same_csv_format(app, archivo):
    teclas(app, "Down", "Right", "2")
    editor(app).key("Enter")
    app.find("Button", text="Guardar").click()
    app.wait(until=lambda: not app.get("modificada"))
    assert archivo.read_text(encoding="utf-8").splitlines()[1] == "Pan,2,4,=B2*C2"
    assert app.get("titulo") == "compra.csv — Hoja"
