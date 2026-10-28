"""Reto 6 (docs/challenges_to_test.md): gestor de proyectos, probado como un usuario.

Dos proyectos y tres personas en un JSON temporal (GESTOR_FILE). Cubre la navegación del
núcleo (secciones que conservan su estado, páginas apiladas, enlaces entre secciones,
before_leave), {#hidden} en las pestañas, el deshacer común y que se guarda en el archivo.
"""
import json
from pathlib import Path

import pytest

from janelkit.inspect import mount

GESTOR = Path(__file__).parent.parent / "examples" / "challenges" / "gestor"


def tarjeta(ident, titulo, **campos):
    return {"id": ident, "titulo": titulo, "descripcion": "", "etiquetas": [], "responsable": "", "fecha": "", **campos}


def proyecto(pid, nombre, miembros, columnas):
    return {"id": pid, "nombre": nombre, "color": "#1971c2", "descripcion": "", "archivado": False,
            "miembros": [{"persona": u, "rol": "Colaborador"} for u in miembros],
            "etiquetas": {"error": "#e03131", "mejora": "#2f9e44"},
            "columnas": [{"id": f"{pid}c{i + 1}", "nombre": n, "tarjetas": ts} for i, (n, ts) in enumerate(columnas)]}


DATOS = {
    "personas": [
        {"id": "u1", "nombre": "Ana García", "color": "#1971c2", "correo": "ana@x.org", "rol": "Responsable"},
        {"id": "u2", "nombre": "Luis Pérez", "color": "#2f9e44", "correo": "luis@x.org", "rol": "Colaborador"},
        {"id": "u3", "nombre": "Marta Ruiz", "color": "#e8590c", "correo": "", "rol": ""},
    ],
    "proyectos": [
        proyecto("p1", "Web", ["u1", "u2"], [
            ("Pendiente", [tarjeta("t1", "Alfa", responsable="u1", etiquetas=["error"]), tarjeta("t2", "Beta")]),
            ("Hecho", [tarjeta("t3", "Gamma", responsable="u2")]),
        ]),
        proyecto("p2", "App", ["u1"], [
            ("Pendiente", [tarjeta("t4", "Delta", responsable="u1", fecha="2026-11-02")]),
            ("Hecho", []),
        ]),
    ],
}  # fmt: skip


@pytest.fixture
def archivo(tmp_path, monkeypatch):
    f = tmp_path / "datos.json"
    f.write_text(json.dumps(DATOS, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("GESTOR_FILE", str(f))
    monkeypatch.delenv("GESTOR_DEMO", raising=False)
    return f


@pytest.fixture
def app(archivo):
    with mount(GESTOR / "src" / "App.janel") as app:
        yield app


def seccion(app, nombre):
    app.find("flex", label=nombre).click()
    app.wait(0.2)


def abrir_proyecto(app, nombre):
    app.find("flex", label=nombre).click()
    app.wait(0.2)
    return app.get("secciones")["proyectos"].page


def pestaña(app, nombre):
    app.find("flex", label=nombre).click()
    app.wait(0.05)


def tarjetas(app):
    return [t.label for t in app.find_all("Tarjeta")]


def resaltadas(app):
    """Las tarjetas que no atenúa el filtro (el filtro del reto 3 atenúa, no oculta)."""
    return [t.label for t in app.find_all("Tarjeta") if t.item.property("opacity") > 0.5]


def test_inicio_muestra_los_proyectos_con_su_resumen(app):
    textos = app.texts()
    assert "Web" in textos and "App" in textos
    assert "3 tarjetas · 2 miembros" in textos and "33 %" in textos
    assert "1 tarjeta · 1 miembro" in textos and "0 %" in textos


def test_abrir_un_proyecto_y_volver_conserva_la_busqueda(app):
    app.find("TextField", label="Buscar proyectos").type("we")
    app.wait(0.05)
    assert "App" not in app.texts()
    abrir_proyecto(app, "Web")
    nav = app.get("secciones")["proyectos"]
    assert nav.current == "Proyecto" and tarjetas(app) == ["Alfa", "Beta", "Gamma"]
    assert "Ana" in app.texts()  # el responsable (un id) se muestra por su nombre
    app.find("Button", text="← Proyectos").click()
    app.wait(0.2)
    assert nav.depth == 1 and app.find("TextField", label="Buscar proyectos").text == "we"


def test_las_secciones_conservan_su_estado(app):
    abrir_proyecto(app, "Web")
    seccion(app, "Personas")
    app.find("TextField", label="Buscar personas").type("mar")
    app.wait(0.05)
    assert "1 de 3" in app.texts()
    seccion(app, "Proyectos")
    assert app.get("secciones")["proyectos"].current == "Proyecto" and "Alfa" in tarjetas(app)
    seccion(app, "Personas")
    assert "1 de 3" in app.texts()


def test_las_pestañas_se_conservan_con_hidden(app):
    pagina = abrir_proyecto(app, "Web")
    app.find("TextField", label="Buscar").type("alf")
    app.wait(0.2)  # transición de opacidad
    assert resaltadas(app) == ["Alfa"]
    pestaña(app, "Miembros")
    assert "Ana García" in app.texts() and "Alfa" not in app.texts()
    pestaña(app, "Tablero")
    app.wait(0.2)
    assert resaltadas(app) == ["Alfa"] and pagina.namespace["texto"].value == "alf"


def test_miembros_cambiar_el_rol_y_quitar_con_aviso(app):
    datos = app.get("datos")
    abrir_proyecto(app, "Web")
    pestaña(app, "Miembros")
    app.find("Select", label="Rol de Luis Pérez").choose("Observador")
    assert datos.proyecto("p1")["miembros"][1] == {"persona": "u2", "rol": "Observador"}
    app.find_all("Button", text="Quitar")[1].click()  # la fila de Luis (la segunda)
    app.wait(0.05)
    assert "1 tarjeta en este proyecto" in app.dialogs()[-1].property("text")
    app.answer_dialog(True)
    app.wait(0.05)
    assert [m["persona"] for m in datos.proyecto("p1")["miembros"]] == ["u1"]
    assert datos.tablero("p1").tarjeta("t3")["responsable"] == ""
    app.key("Ctrl+Z")  # un solo paso: vuelve el miembro y su tarjeta
    app.wait(0.05)
    assert datos.proyecto("p1")["miembros"][1]["rol"] == "Observador" and datos.tablero("p1").tarjeta("t3")["responsable"] == "u2"


def test_renombrar_a_una_persona_se_ve_en_los_tableros(app):
    seccion(app, "Personas")
    app.find("flex", label="Ana García").click()
    app.wait(0.2)
    campo = app.find("TextField", label="Nombre")
    campo.type("Anabel Gómez")
    app.wait(0.05)
    app.find("Button", text="Guardar").click()
    app.wait(0.05)
    assert app.get("datos").nombre("u1") == "Anabel Gómez"
    assert "Alfa" in app.texts() and "Delta" in app.texts()  # sus tarjetas, en los dos proyectos
    seccion(app, "Proyectos")
    abrir_proyecto(app, "Web")
    assert "Anabel" in app.texts() and "Ana" not in app.texts()  # el responsable de Alfa, por su nombre de pila


def test_dar_de_baja_avisa_y_se_puede_deshacer(app):
    datos = app.get("datos")
    seccion(app, "Personas")
    app.find("flex", label="Ana García").click()
    app.wait(0.2)
    app.find("Button", text="Dar de baja").click()
    app.wait(0.05)
    assert "2 tarjetas" in app.dialogs()[-1].property("text")
    app.answer_dialog(True)
    app.wait(0.2)
    assert datos.persona("u1") is None and app.get("secciones")["personas"].depth == 1
    assert [m["persona"] for m in datos.proyecto("p1")["miembros"]] == ["u2"]
    assert datos.tablero("p1").tarjeta("t1")["responsable"] == ""
    assert app.get("deshacer").startswith("quitar a «Ana García»")
    app.key("Ctrl+Z")
    app.wait(0.05)
    assert datos.nombre("u1") == "Ana García" and datos.tablero("p2").tarjeta("t4")["responsable"] == "u1"
    assert [m["persona"] for m in datos.proyecto("p1")["miembros"]] == ["u1", "u2"]


def test_deshacer_es_comun_a_todas_las_secciones(app):
    datos = app.get("datos")
    abrir_proyecto(app, "Web")
    app.find("Tarjeta", label="Beta").drag_to(app.find("Columna", label="Hecho"))
    app.wait(0.05)
    assert datos.resumen(datos.proyecto("p1"))["progreso"] == 2 / 3
    seccion(app, "Personas")
    app.find("Button", text="Deshacer").click()
    app.wait(0.05)
    assert [t["titulo"] for t in datos.proyecto("p1")["columnas"][1]["tarjetas"]] == ["Gamma"]
    app.key("Ctrl+Y")
    app.wait(0.05)
    assert len(datos.proyecto("p1")["columnas"][1]["tarjetas"]) == 2


def test_mi_trabajo_lleva_a_la_tarjeta_en_su_tablero(app):
    seccion(app, "Mi trabajo")
    assert app.find("flex", label="Delta") and app.find("flex", label="Alfa")  # Ana: en los dos proyectos
    app.find("flex", label="Delta").click()
    app.wait(0.3)
    secciones = app.get("secciones")
    nav = secciones["proyectos"]
    assert secciones.current == "proyectos" and nav.current == "Proyecto" and nav.depth == 2
    assert nav.page.namespace["ident"].value == "p2" and tarjetas(app) == ["Delta"]
    assert app.window.activeFocusItem() is app.find("Tarjeta", label="Delta").item
    # Con el proyecto ya abierto, el enlace solo enfoca (no apila otra página).
    seccion(app, "Mi trabajo")
    app.find("flex", label="Delta").click()
    app.wait(0.3)
    assert nav.depth == 2


def test_salir_con_un_detalle_sin_guardar_pregunta(app):
    abrir_proyecto(app, "Web")
    app.find("Tarjeta", label="Alfa").key("Return")
    app.wait(0.1)
    app.find("TextField", label="Título").type(" editado")
    app.wait(0.05)
    nav = app.get("secciones")["proyectos"]
    app.find("Button", text="← Proyectos").click()
    app.wait(0.1)
    assert app.dialogs(), "debía preguntar"
    app.answer_dialog(False)
    app.wait(0.1)
    assert nav.depth == 2
    app.find("Button", text="← Proyectos").click()
    app.wait(0.1)
    app.answer_dialog(True)
    app.wait(0.2)
    assert nav.depth == 1 and app.get("datos").tablero("p1").tarjeta("t1")["titulo"] == "Alfa"


def test_proyecto_nuevo_archivar_y_guardar_en_el_archivo(app, archivo):
    datos = app.get("datos")
    app.find("Button", text="+ Proyecto").click()
    app.wait(0.2)
    nav = app.get("secciones")["proyectos"]
    assert nav.current == "Proyecto" and [c["nombre"] for c in nav.page.namespace["columnas"].value] == ["Pendiente", "En curso", "Hecho"]
    pestaña(app, "Ajustes")
    app.find("Button", text="Archivar").click()
    app.wait(0.05)
    nuevo = datos.proyectos.peek()[-1]
    assert nuevo["archivado"] and "Archivado" in app.texts()
    app.wait(0.5)  # el guardado espera a que acabe la ráfaga de cambios
    guardado = json.loads(archivo.read_text(encoding="utf-8"))
    assert [p["nombre"] for p in guardado["proyectos"]] == ["Web", "App", "Proyecto nuevo"]
    assert guardado["proyectos"][-1]["archivado"] is True


def test_importar_el_tablero_del_kanban(app):
    from services.datos import importar_kanban  # importado con la app montada: `mount` lo olvida al salir

    personas = [{"id": "u1", "nombre": "Ana", "color": "", "correo": "", "rol": ""}]
    kanban = {"columnas": [{"id": "c1", "nombre": "Pendiente", "tarjetas": [
        tarjeta("t1", "A", responsable="Ana"), tarjeta("t2", "B", responsable="Luis"), tarjeta("t3", "C")]}]}
    p = importar_kanban(kanban, personas, pid="p9")
    assert [t["responsable"] for t in p["columnas"][0]["tarjetas"]] == ["u1", "u-k2", ""]
    assert [x["nombre"] for x in personas] == ["Ana", "Luis"] and p["columnas"][0]["id"] == "p9c1"
    assert {m["persona"] for m in p["miembros"]} == {"u1", "u-k2"}


def test_crear_una_columna_desde_el_tablero_y_nombrarla(app):
    datos = app.get("datos")
    abrir_proyecto(app, "Web")
    app.find("flex", label="Añadir columna").click()  # el hueco al final de las columnas
    app.wait(0.1)
    campo = app.find("TextField", label="Nombre de la columna")  # empieza con el nombre en edición
    assert app.window.activeFocusItem() is not None and campo.item.property("activeFocus")
    campo.type("Bloqueadas").submit()
    app.wait(0.05)
    assert [c["nombre"] for c in datos.proyecto("p1")["columnas"]] == ["Pendiente", "Hecho", "Bloqueadas"]
    app.find("Button", text="+ Columna").click()  # el botón de la barra hace lo mismo
    app.wait(0.1)
    app.find("TextField", label="Nombre de la columna").type("Revisión").submit()
    app.wait(0.05)
    assert datos.proyecto("p1")["columnas"][-1]["nombre"] == "Revisión"
