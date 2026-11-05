"""API pública de janelkit-i18n, su versión y su serie (docs/api.md, política de versiones).

La serie (los dos primeros números) es la del núcleo: janelkit-i18n 0.2.x.x va con janelkit 0.2.x.x.
"""
import re
from importlib.metadata import requires, version

from packaging.requirements import Requirement

import janelkit
import janelkit_i18n

PUBLIC = ["I18n", "I18nError", "__version__", "i18n", "t"]


def test_exports_are_exactly_the_public_api():
    assert sorted(janelkit_i18n.__all__) == sorted(PUBLIC)
    for name in PUBLIC:
        assert hasattr(janelkit_i18n, name), name


def test_the_version_has_four_numbers_and_the_series_of_the_core():
    assert re.fullmatch(r"\d+\.\d+\.\d+\.\d+", janelkit_i18n.__version__)
    assert janelkit_i18n.__version__.split(".")[:2] == janelkit.__version__.split(".")[:2]


def test_the_installed_metadata_matches_the_code():
    assert version("janelkit-i18n") == janelkit_i18n.__version__, "reinstala el paquete (pip install -e)"


def test_it_asks_for_exactly_the_series_of_the_installed_core():
    (core,) = [Requirement(r) for r in requires("janelkit-i18n") if Requirement(r).name == "janelkit"]
    major, series = (int(n) for n in janelkit.__version__.split(".")[:2])
    assert version("janelkit") in core.specifier
    assert f"{major}.{series + 1}.0.0" not in core.specifier
    assert series == 0 or f"{major}.{series - 1}.99.99" not in core.specifier
