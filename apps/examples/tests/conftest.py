import os

import pytest

# Fixtures compartidas: janel_app, mount y el aislamiento entre pruebas.
from janelkit.testing import isolated_data, janel_app, mount, reset_theme_and_locale


@pytest.fixture(autouse=True, scope="session")
def example_data(tmp_path_factory):
    """Los ejemplos que guardan datos (apps/examples/compra) escriben en una carpeta temporal, no en $HOME."""
    os.environ["COMPRA_FILE"] = str(tmp_path_factory.mktemp("datos") / "lista-compra.json")
    yield


@pytest.fixture(autouse=True)
def reset_i18n():
    from janelkit_i18n import i18n

    yield
    i18n.reset()

__all__ = ["isolated_data", "janel_app", "mount", "reset_theme_and_locale"]
