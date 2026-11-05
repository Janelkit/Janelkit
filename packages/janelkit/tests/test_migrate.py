"""`janel migrate` (0.2): actualiza un proyecto de 0.1 a la serie 0.2.

Elementos en minúscula, imports de lo que salió del núcleo (janelkit-router, janelkit-store),
avisos de lo que hay que revisar a mano (History) y, con `--tests`, las pruebas.
"""
from janelkit.cli.main import main
from janelkit.cli.migrate import migrate_janel, migrate_python
from janelkit.compiler import compile_file

JANEL_01 = """<script>
from components.Tarjeta import Tarjeta
from components.Text import Text
from janelkit import History, state
</script>
<Window title="x">
  <Column class="raiz">
    <Text>propio</Text>
    <Tarjeta><Button on:click={n += 1}>+</Button></Tarjeta>
    <TextField bind:value={n} />
    <Slot />
  </Column>
</Window>
<style>
Column > Button:hover, .Text, Text { color: red; }
/* Button en un comentario */
.raiz { font-family: Text; }
</style>
"""


def test_migrate_janel_renames_tags_and_selectors_but_not_imported_components():
    new, notes = migrate_janel(JANEL_01)
    assert "<window title" in new and "</window>" in new and "<column class" in new and "</column>" in new
    assert "<Text>propio</Text>" in new  # es un componente importado
    assert "<button on:click={n += 1}>+</button>" in new and "<textfield bind" in new and "<slot />" in new
    assert "column > button:hover, .Text, Text { color: red; }" in new  # Text es el componente
    assert "/* Button en un comentario */" in new and "font-family: Text;" in new
    assert "from components.Text import Text" in new  # el script no se toca
    assert any("History se quitó" in n for n in notes)
    assert migrate_janel(new) == (new, notes)  # aplicarlo dos veces no cambia nada


def test_migrate_python_updates_templates_and_find_in_tests():
    src = 'SRC = "<Column><Text>a</Text></Column>\\n<style>Text { color: red; }</style>"\nel = app.find("Button")\napp.find_all(\'Text\', text="a")\n'
    new, notes = migrate_python(src)
    assert new == 'SRC = "<column><text>a</text></column>\\n<style>text { color: red; }</style>"\nel = app.find("button")\napp.find_all(\'text\', text="a")\n'
    assert notes == []


def test_janel_migrate_shows_a_diff_and_writes_only_with_write(tmp_path, capsys):
    app = tmp_path / "src" / "App.janel"
    app.parent.mkdir()
    app.write_text("<Window><Text>hola</Text></Window>\n", encoding="utf-8")
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "Otro.janel").write_text("<Text>no</Text>", encoding="utf-8")
    assert main(["migrate", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "-<Window><Text>hola</Text></Window>" in out and "+<window><text>hola</text></window>" in out
    assert "1 de 1 archivo(s) cambiarían" in out
    assert app.read_text(encoding="utf-8") == "<Window><Text>hola</Text></Window>\n"
    assert main(["migrate", str(tmp_path), "--write"]) == 0
    assert app.read_text(encoding="utf-8") == "<window><text>hola</text></window>\n"
    assert (tmp_path / ".venv" / "lib" / "Otro.janel").read_text(encoding="utf-8") == "<Text>no</Text>"
    assert compile_file(app).warnings == []


def test_migrate_moves_the_navigation_imports_to_janelkit_router():
    src = """<script>
from janelkit import state, pages, navigation as nav_de  # navegación
from Inicio import Inicio
nav = pages(Inicio)
</script>
<Column><Pages stack={nav} /></Column>
"""
    new, _ = migrate_janel(src)
    assert "from janelkit import state\nfrom janelkit_router import pages, navigation as nav_de, Pages  # navegación\n" in new
    assert "<column><Pages stack={nav} /></column>" in new
    assert migrate_janel(new)[0] == new
    only, _ = migrate_janel("<script>\nfrom janelkit import sections\ns = sections()\n</script>\n<Sections of={s} />\n")
    assert "\nfrom janelkit_router import sections, Sections\n" in only and "from janelkit import" not in only
    py, _ = migrate_python("from janelkit import PageStack, Sections\n")
    assert py == "from janelkit_router import PageStack, SectionSet\n"


def test_migrate_moves_persisted_to_janelkit_store():
    py, _ = migrate_python("from janelkit import state, persisted, pages\n")
    assert py == "from janelkit import state\nfrom janelkit_store import persisted\nfrom janelkit_router import pages\n"



def test_janel_migrate_updates_the_tests_only_with_tests(tmp_path, capsys):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "App.janel").write_text("<Text>hola</Text>\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    prueba = tmp_path / "tests" / "test_app.py"
    prueba.write_text('assert app.find("Text").text == "hola"\nSRC = "<Button>ok</Button>"\n', encoding="utf-8")
    servicio = tmp_path / "src" / "servicio.py"
    servicio.write_text('NOMBRE = "<Text>"\n', encoding="utf-8")  # no es una prueba: no se toca
    assert main(["migrate", str(tmp_path), "--write"]) == 0
    assert 'find("Text")' in prueba.read_text(encoding="utf-8")
    assert main(["migrate", str(tmp_path), "--write", "--tests"]) == 0
    assert prueba.read_text(encoding="utf-8") == 'assert app.find("text").text == "hola"\nSRC = "<button>ok</button>"\n'
    assert servicio.read_text(encoding="utf-8") == 'NOMBRE = "<Text>"\n'
    assert "1 de 2 archivo(s) cambiados" in capsys.readouterr().out


def test_janel_migrate_lists_what_needs_a_human(tmp_path, capsys):
    app = tmp_path / "App.janel"
    app.write_text("<script>\nfrom janelkit import History\n</script>\n<text>x</text>\n", encoding="utf-8")
    assert main(["migrate", str(app)]) == 0
    assert "revisar a mano: History se quitó en la 0.2" in capsys.readouterr().out


def test_janel_migrate_on_a_missing_path_fails(tmp_path, capsys):
    assert main(["migrate", str(tmp_path / "no_existe")]) == 1
    assert "no existe" in capsys.readouterr().out
