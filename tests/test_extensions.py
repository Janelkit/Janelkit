"""Frontera entre el núcleo y las extensiones, y los puntos de extensión que la hacen posible."""
import ast
import time
from pathlib import Path

import pytest
from conftest import find

import janelkit
from janelkit import locale
from janelkit.cli import main as cli
from janelkit.ext import inspector
from janelkit.inspect import MountedApp, add_inspector

PACKAGE = Path(janelkit.__file__).parent

# Módulos que aún viven en el paquete pero saldrán a janelkit-i18n y janelkit-desktop
# (docs/alcance.md). Deben usar solo la API pública, como cualquier paquete externo.
EXTENSIONS = {"i18n", "dialogs", "clipboard", "notifications"}
PUBLIC_MODULES = {"janelkit.ext", "janelkit.inspect", "janelkit.compiler", "janelkit.diagnostics"}


def module_name(path: Path) -> str:
    parts = path.relative_to(PACKAGE.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def imports(path: Path) -> list[tuple[str, list[str], int]]:
    """(módulo absoluto, nombres importados, nivel relativo) de cada import del archivo."""
    package = module_name(path).split(".")
    if path.name != "__init__.py":
        package = package[:-1]
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [(alias.name, [], 0) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = package[: len(package) - node.level + 1] if node.level else []
            target = ".".join([*base, *([node.module] if node.module else [])])
            out.append((target, [alias.name for alias in node.names], node.level))
    return out


def touches_extension(target: str, names: list[str]) -> bool:
    if target in {f"janelkit.{e}" for e in EXTENSIONS}:
        return True
    return target == "janelkit" and bool(EXTENSIONS & set(names))


def test_the_core_does_not_import_the_extensions():
    offenders = []
    for path in PACKAGE.rglob("*.py"):
        if path.stem in EXTENSIONS and path.parent == PACKAGE or path == PACKAGE / "__init__.py":
            continue  # __init__ las reexporta mientras sigan en el paquete
        for target, names, _ in imports(path):
            if touches_extension(target, names):
                offenders.append(f"{path.relative_to(PACKAGE)} importa {target} {names}")
    assert offenders == []


def test_extensions_only_use_the_public_api():
    offenders = []
    for stem in sorted(EXTENSIONS):
        path = PACKAGE / f"{stem}.py"
        for target, names, level in imports(path):
            if level:
                offenders.append(f"{stem}: import relativo de {target}")
            elif target == "janelkit":
                offenders += [f"{stem}: janelkit.{n} no es público" for n in names if n not in janelkit.__all__]
            elif target.startswith("janelkit") and target not in PUBLIC_MODULES:
                offenders.append(f"{stem}: {target} es interno")
    assert offenders == []


# -- janelkit.ext.inspector ------------------------------------------------------------------
def test_an_extension_adds_methods_to_mounted_app():
    seen = []

    @inspector("say_hello_for_test")
    def say(app, name):
        seen.append((app, name))
        return f"hola {name}"

    app = MountedApp(application=None, mounted=None)
    assert app.say_hello_for_test("Ana") == "hola Ana" and seen == [(app, "Ana")]
    with pytest.raises(AttributeError, match="si lo añade una extensión"):
        app.not_registered()
    with pytest.raises(ValueError, match="ya tiene 'find'"):
        add_inspector("find", say)


def test_dialogs_and_notifications_are_inspector_extensions():
    app = MountedApp(application=None, mounted=None)
    assert app.dialogs() == [] and isinstance(app.notifications(), list)


# -- janelkit.locale: la dirección es del núcleo; i18n solo la cambia -------------------------
APP = """<Window width={300} height={100}>
  <Row id="row"><Text id="a">uno</Text><Spacer /><Text>dos</Text></Row>
</Window>
"""


def test_locale_mirrors_the_layout_without_translations(mount, janel_app):
    m = mount(APP)
    a, row = find(m, "a"), find(m, "row")
    locale.set("he")
    for _ in range(5):
        janel_app.process_events()
        time.sleep(0.01)
    assert locale.rtl and janelkit.i18n.rtl and a.x() > row.width() / 2
    locale.reset()
    for _ in range(5):
        janel_app.process_events()
        time.sleep(0.01)
    assert not locale.rtl and a.x() < row.width() / 2


# -- plugins de la CLI ---------------------------------------------------------------------
class FakeEntryPoint:
    def __init__(self, name, target):
        self.name, self.value, self._target = name, f"demo:{name}", target

    def load(self):
        if isinstance(self._target, Exception):
            raise self._target
        return self._target


def configure_greet(parser):
    """saluda desde un plugin"""
    parser.add_argument("who")
    parser.set_defaults(func=lambda args: print(f"hola {args.who}") or 7)


def test_cli_runs_commands_from_other_packages(monkeypatch, capsys):
    monkeypatch.setattr(cli, "_plugin_commands", lambda: [FakeEntryPoint("greet", configure_greet)])
    assert cli.main(["greet", "Ana"]) == 7
    assert capsys.readouterr().out == "hola Ana\n"
    assert "saluda desde un plugin" in cli.build_parser().format_help()


def test_cli_survives_broken_or_clashing_plugins(monkeypatch, capsys):
    plugins = [FakeEntryPoint("broken", ImportError("falta algo")), FakeEntryPoint("new", configure_greet)]
    monkeypatch.setattr(cli, "_plugin_commands", lambda: plugins)
    help_text = cli.build_parser().format_help()
    err = capsys.readouterr().err
    assert "no se pudo cargar el comando 'broken'" in err and "falta algo" in err
    assert "no puede redefinir el comando 'new'" in err
    assert "broken" not in help_text
