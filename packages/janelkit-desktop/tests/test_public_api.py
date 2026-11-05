"""API pública de janelkit-desktop, su versión y su serie (docs/api.md, política de versiones).

La serie (los dos primeros números) es la del núcleo: janelkit-desktop 0.2.x.x va con janelkit 0.2.x.x.
"""
import re
from importlib.metadata import requires, version

import pytest
from packaging.requirements import Requirement

import janelkit
import janelkit_desktop
from janelkit.inspect import mount

PUBLIC = ["__version__", "clipboard", "dialogs"]


def test_exports_are_exactly_the_public_api():
    assert sorted(janelkit_desktop.__all__) == sorted(PUBLIC)
    for name in PUBLIC:
        assert hasattr(janelkit_desktop, name), name


def test_the_version_has_four_numbers_and_the_series_of_the_core():
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", janelkit_desktop.__version__)
    assert janelkit_desktop.__version__.split(".")[:2] == janelkit.__version__.split(".")[:2]


def test_the_installed_metadata_matches_the_code():
    assert version("janelkit-desktop") == janelkit_desktop.__version__, "reinstala el paquete (pip install -e)"


def test_it_asks_for_exactly_the_series_of_the_installed_core():
    (core,) = [Requirement(r) for r in requires("janelkit-desktop") if Requirement(r).name == "janelkit"]
    major, series = (int(n) for n in janelkit.__version__.split(".")[:2])
    assert version("janelkit") in core.specifier
    assert f"{major}.{series + 1}.0.0" not in core.specifier
    assert series == 0 or f"{major}.{series - 1}.99.99" not in core.specifier


@pytest.mark.parametrize("name", ["notify", "notifications"])
def test_the_notifications_were_removed_with_an_explanation(name):
    with pytest.raises(ImportError, match="se quitó de janelkit-desktop en la 0.2"):
        exec(f"from janelkit_desktop import {name}")


def test_inspect_gets_dialogs_but_no_longer_notifications(tmp_path):
    (tmp_path / "App.janel").write_text("<text>hola</text>", encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        assert app.dialogs() == []  # la añade janelkit-desktop
        with pytest.raises(AttributeError, match="no tiene 'notifications'"):
            app.notifications()
