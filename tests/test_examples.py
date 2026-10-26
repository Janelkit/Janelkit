"""Los ejemplos del repositorio deben seguir compilando sin advertencias."""
from pathlib import Path

import pytest

from fluxui.compiler import compile_file

EXAMPLES = sorted((Path(__file__).parent.parent / "examples").glob("*/src/App.flux"))


@pytest.mark.parametrize("app", EXAMPLES, ids=lambda p: p.parent.parent.name)
def test_example_compiles(app):
    assert compile_file(app).warnings == []


@pytest.mark.parametrize("app", EXAMPLES, ids=lambda p: p.parent.parent.name)
def test_example_mounts(app, flux_app):
    from fluxui.compiler import compile_file

    m = flux_app.mount(compile_file(app))
    flux_app.unmount(m)


def test_there_are_examples():
    assert EXAMPLES
