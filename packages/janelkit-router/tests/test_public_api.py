"""API pública de janelkit-router, su versión y su serie (docs/api.md, política de versiones).

La serie (los dos primeros números) es la del núcleo: janelkit-router 0.2.x.x va con janelkit 0.2.x.x.
"""
import re
from importlib.metadata import requires, version

from packaging.requirements import Requirement

import janelkit
import janelkit_router
from janelkit.inspect import mount

PUBLIC = ["PageStack", "SectionSet", "__version__", "navigation", "pages", "sections"]


def test_exports_are_exactly_the_public_api():
    assert sorted(janelkit_router.__all__) == sorted(PUBLIC)
    for name in PUBLIC:
        assert hasattr(janelkit_router, name), name


def test_the_version_has_four_numbers_and_the_series_of_the_core():
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", janelkit_router.__version__)
    assert janelkit_router.__version__.split(".")[:2] == janelkit.__version__.split(".")[:2]


def test_the_installed_metadata_matches_the_code():
    assert version("janelkit-router") == janelkit_router.__version__, "reinstala el paquete (pip install -e)"


def test_it_asks_for_exactly_the_series_of_the_installed_core():
    (core,) = [Requirement(r) for r in requires("janelkit-router") if Requirement(r).name == "janelkit"]
    major, series = (int(n) for n in janelkit.__version__.split(".")[:2])
    assert version("janelkit") in core.specifier
    assert f"{major}.{series + 1}.0.0" not in core.specifier
    assert series == 0 or f"{major}.{series - 1}.99.99" not in core.specifier


def test_sections_and_pages_give_their_public_types(tmp_path):
    (tmp_path / "Inicio.janel").write_text("<text>inicio</text>", encoding="utf-8")
    (tmp_path / "App.janel").write_text(
        "<script>\nfrom janelkit_router import Pages, Sections, pages, sections\nfrom Inicio import Inicio\n"
        "s = sections(a=Inicio)\nnav = pages(Inicio)\n</script>\n<column><Sections of={s} /><Pages stack={nav} /></column>",
        encoding="utf-8")
    with mount(tmp_path / "App.janel") as app:
        assert isinstance(app.get("s"), janelkit_router.SectionSet)
        assert isinstance(app.get("nav"), janelkit_router.PageStack)
        assert app.texts() == ["inicio", "inicio"]
