"""persisted(clave, valor): estado que se recuerda entre sesiones (janelkit/storage.py)."""
import json
import tempfile
from pathlib import Path

import pytest

from janelkit import Persisted, computed, persisted, storage
from janelkit.inspect import mount


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv(storage.DATA_ENV, str(tmp_path))
    storage.use_app(tmp_path / "App.janel")
    yield tmp_path
    storage.flush_all()
    storage._registry.clear()


def saved(folder: Path, key: str):
    return json.loads((folder / f"{key}.json").read_text(encoding="utf-8"))


def test_reads_the_initial_value_saves_changes_and_reads_them_back(data):
    tema = persisted("prefs.tema", "claro")
    assert isinstance(tema, Persisted) and tema.value == "claro"
    assert not (data / "prefs.tema.json").exists()  # nada que guardar hasta que cambie
    seen = computed(lambda: tema.value.upper())
    tema.value = "oscuro"
    assert seen.value == "OSCURO"  # sigue siendo un state reactivo
    tema.flush()
    assert saved(data, "prefs.tema") == "oscuro"
    storage.use_app(data / "App.janel")  # otra sesión
    assert persisted("prefs.tema", "claro").value == "oscuro"


def test_changes_in_place_are_saved(data):
    recientes = persisted("recientes", [])
    recientes.value.append({"ruta": "a.txt", "abierto": False})
    recientes.value[0]["abierto"] = True
    recientes.flush()
    assert saved(data, "recientes") == [{"ruta": "a.txt", "abierto": True}]


def test_same_key_is_the_same_object(data):
    a = persisted("contador", 1)
    b = persisted("contador", 99)
    assert a is b and b.value == 1


def test_bad_keys_values_and_files(data, caplog):
    with pytest.raises(ValueError):
        persisted("../fuera", 1)
    with pytest.raises(TypeError):
        persisted("conjunto", {1, 2})
    roto = data / "roto.json"
    roto.write_text("{no es json", encoding="utf-8")
    assert persisted("roto", {"ok": True}).value == {"ok": True}
    assert "no es JSON" in caplog.text
    valor = persisted("valor", 1)
    with pytest.raises(TypeError):
        valor.value = object()


def test_in_an_app_writes_are_grouped_and_mount_uses_a_temporary_folder(monkeypatch):
    monkeypatch.delenv(storage.DATA_ENV, raising=False)
    d = Path(tempfile.mkdtemp()) / "notas" / "src"
    d.mkdir(parents=True)
    (d / "App.janel").write_text("""<script>
from janelkit import persisted
n = persisted("n", 0)
</script>
<Column><Button text={f"n={n}"} on:click={n += 1} /></Column>""", encoding="utf-8")
    with mount(d / "App.janel") as app:
        folder = storage.data_folder()
        assert folder.name.startswith("janelkit-data-")  # no la carpeta real del usuario
        for _ in range(3):
            app.find("Button").click()
        assert not (folder / "n.json").exists()  # agrupado: todavía no se ha escrito
        app.wait(0.4)
        assert saved(folder, "n") == 3
        assert app.find("Button").item.property("text") == "n=3"
    assert not folder.exists()  # se borra al desmontar


def test_app_name_comes_from_the_project_folder(monkeypatch):
    monkeypatch.delenv(storage.DATA_ENV, raising=False)
    storage.use_app(Path("/x/gestor/src/App.janel"))
    assert storage.data_folder().name == "gestor"
    storage.use_app(Path("/x/contador/App.janel"))
    assert storage.data_folder().name == "contador"
