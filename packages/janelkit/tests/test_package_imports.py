"""Componentes (.janel) y elementos (.qml) que vienen en un paquete de Python instalado."""
import sys
from pathlib import Path

import pytest

from janelkit.cli.build import build_project
from janelkit.compiler import compile_file
from janelkit.inspect import mount

TARJETA = """<script>
from janelkit import prop
from .Medidor import Medidor
from mi_ui.sub.Etiqueta import Etiqueta
titulo = prop("")
</script>
<column class="tarjeta">
  <Etiqueta texto={titulo} />
  <Medidor value={3} />
</column>
"""

MEDIDOR = """import QtQuick
Rectangle {
    property real value: 0
    implicitWidth: 40; implicitHeight: 8
}
"""

ETIQUETA = """<script>
from janelkit import prop
texto = prop("")
</script>
<text>{texto}</text>
"""

APP = """<script>
from mi_ui import Tarjeta
from mi_ui import Medidor
</script>
<window><column>
  <Tarjeta titulo="Hola" />
  <Medidor value={1} />
</column></window>
"""


@pytest.fixture
def paquete(tmp_path, monkeypatch):
    pkg = tmp_path / "site" / "mi_ui"
    (pkg / "sub").mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "sub" / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "Tarjeta.janel").write_text(TARJETA, encoding="utf-8")
    (pkg / "Medidor.qml").write_text(MEDIDOR, encoding="utf-8")
    (pkg / "sub" / "Etiqueta.janel").write_text(ETIQUETA, encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path / "site"))
    app = tmp_path / "proyecto" / "src" / "App.janel"
    app.parent.mkdir(parents=True)
    app.write_text(APP, encoding="utf-8")
    return app


def test_components_and_qml_elements_from_an_installed_package_compile(paquete):
    c = compile_file(paquete)
    assert c.all_warnings == []
    assert {"Tarjeta.janel", "Etiqueta.janel"} <= {Path(f).name for f in c.files}


def test_they_mount_and_render(paquete):
    with mount(paquete) as app:
        assert app.find("Tarjeta").visible
        assert app.find("text", text="Hola").visible
        assert len(app.find_all("Medidor")) == 2


def test_an_unknown_name_in_a_package_is_still_a_normal_import(paquete):
    paquete.write_text("<script>\nfrom mi_ui import NoExiste\n</script>\n<window><NoExiste /></window>", encoding="utf-8")
    with pytest.raises(Exception) as exc:
        compile_file(paquete)
    assert "elemento desconocido <NoExiste>" in str(exc.value)


def test_a_name_that_only_differs_in_case_from_a_component_is_a_normal_import(paquete):
    # En Windows y macOS el disco no distingue mayúsculas: `medidor` no es `Medidor.qml`.
    # Así se importa `sections` de janelkit_router, que también trae `Sections.qml`.
    (paquete.parents[2] / "site" / "mi_ui" / "__init__.py").write_text("def medidor():\n    return 3\n", encoding="utf-8")
    paquete.write_text("<script>\nfrom mi_ui import medidor, Medidor\n</script>\n"
                       "<window><column><text>{medidor()}</text><Medidor value={1} /></column></window>", encoding="utf-8")
    c = compile_file(paquete)
    assert c.all_warnings == []
    try:
        with mount(paquete) as app:
            assert app.find("text", text="3").visible
            assert len(app.find_all("Medidor")) == 1
    finally:  # mount() olvida los módulos de la app, no los del paquete: las demás pruebas usan otro mi_ui
        for name in [m for m in sys.modules if m == "mi_ui" or m.startswith("mi_ui.")]:
            del sys.modules[name]


def test_janel_build_writes_package_components_apart(paquete):
    result = build_project(paquete.parent.parent)
    assert result.ok, result.errors
    written = {p.relative_to(result.out_dir).as_posix() for p in result.written}
    assert "App.qml" in written
    assert "_paquetes/mi_ui/Tarjeta.qml" in written and "_paquetes/mi_ui/sub/Etiqueta.qml" in written
