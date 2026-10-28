"""Puntos de extensión del núcleo: janelkit.ext, plugins de la CLI y el idioma de la interfaz."""
import time

import pytest

from janelkit import locale
from janelkit.cli import main as cli
from janelkit.ext import app, inspector
from janelkit.inspect import MountedApp, add_inspector
from janelkit.testing import find


# -- janelkit.ext ----------------------------------------------------------------------------
def test_app_is_the_running_application(janel_app):
    assert app() is janel_app


def test_an_extension_adds_methods_to_mounted_app():
    seen = []

    @inspector("say_hello_for_test")
    def say(app, name):
        seen.append((app, name))
        return f"hola {name}"

    mounted = MountedApp(application=None, mounted=None)
    assert mounted.say_hello_for_test("Ana") == "hola Ana" and seen == [(mounted, "Ana")]
    with pytest.raises(AttributeError, match="si lo añade una extensión"):
        mounted.not_registered()
    with pytest.raises(ValueError, match="ya tiene 'find'"):
        add_inspector("find", say)


# -- janelkit.locale: la dirección de escritura es del núcleo --------------------------------
APP = """<Window width={300} height={100}>
  <Row id="row"><Text id="a">uno</Text><Spacer /><Text>dos</Text></Row>
</Window>
"""


def settle(janel_app):
    """Los layouts se recolocan en su siguiente pasada: dejar correr el bucle un momento."""
    for _ in range(5):
        janel_app.process_events()
        time.sleep(0.01)


def test_locale_mirrors_the_layout_without_translations(mount, janel_app):
    m = mount(APP)
    a, row = find(m, "a"), find(m, "row")
    locale.set("he")
    settle(janel_app)
    assert locale.rtl and a.x() > row.width() / 2
    locale.reset()
    settle(janel_app)
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
