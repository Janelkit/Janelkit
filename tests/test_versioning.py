"""Versiones calculadas a partir de los prefijos de los commits (tools/versioning.py)."""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("versioning", REPO / "tools" / "versioning.py")
versioning = importlib.util.module_from_spec(_spec)
sys.modules["versioning"] = versioning  # dataclass busca el módulo por su nombre
_spec.loader.exec_module(versioning)

ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
MODULES = {"janelkit": "janelkit", "janelkit-desktop": "janelkit_desktop", "janelkit-store": "janelkit_store"}


def run(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, env=ENV).stdout


def make_package(root: Path, name: str, version: str, deps: str = "") -> None:
    base = root / "packages" / name
    (base / "src" / MODULES[name]).mkdir(parents=True)
    (base / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\ndependencies = [{deps}]\n\n[build-system]\n', encoding="utf-8"
    )
    (base / "src" / MODULES[name] / "__init__.py").write_text(f'"""m"""\n__version__ = "{version}"\n', encoding="utf-8")
    (base / "README.md").write_text(f"# {name}\n\n## Cambios\n\n### {version}\n\n- Primera.\n\n## Licencia\n", encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """janelkit y janelkit-desktop publicados en 0.2.0.0."""
    run(tmp_path, "init", "-q", "-b", "main")
    make_package(tmp_path, "janelkit", "0.2.0.0")
    make_package(tmp_path, "janelkit-desktop", "0.2.0.0", '"janelkit>=0.2,<0.3"')
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "cambios.md").write_text("# Cambios\n\nIntro.\n\n## 0.2.0.0\n\n- Antes.\n", encoding="utf-8")
    run(tmp_path, "add", "-A")
    run(tmp_path, "commit", "-q", "-m", "interno: inicio")
    run(tmp_path, "tag", "janelkit-v0.2.0.0")
    run(tmp_path, "tag", "janelkit-desktop-v0.2.0.0")
    return tmp_path


def commit(root: Path, path: str, message: str) -> None:
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(file.read_text(encoding="utf-8") + "x\n" if file.exists() else "x\n", encoding="utf-8")
    run(root, "add", "-A")
    run(root, "commit", "-q", "-m", message)


def write_version(root: Path, name: str, version: str, message: str | None = None) -> None:
    """Escribe a mano la versión en el pyproject.toml y en __version__ (y hace commit si hay mensaje)."""
    base = root / "packages" / name
    for path, key in ((base / "pyproject.toml", "version"), (base / "src" / MODULES[name] / "__init__.py", "__version__")):
        path.write_text(re.sub(rf'^{key} = "[^"]+"', f'{key} = "{version}"', path.read_text(encoding="utf-8"), flags=re.M),
                        encoding="utf-8")
    if message:
        run(root, "add", "-A")
        run(root, "commit", "-q", "-m", message)


def read(root: Path, path: str) -> str:
    return (root / path).read_text(encoding="utf-8")


def plan(root: Path) -> dict[str, str]:
    return {name: versioning.show(v) for name, v in versioning.compute(root)[1].items()}


@pytest.mark.parametrize("subject, ok", [
    ("mayor: Window con screen", True),
    ("menor: corrige timeout", True),
    ("interno: prueba de capas", True),
    ("docs: guía", True),
    ("version: janelkit 0.2.0.0", True),
    ("Merge branch 'main'", True),
    ("Añade cosas", False),
    ("mayor:sin espacio", False),
    ("feat: algo", False),
])
def test_commit_prefixes(subject, ok):
    assert (versioning.message_problem(subject) is None) is ok


def test_versions_have_four_numbers_and_old_tags_three():
    assert versioning.parse_version("0.2.3.1") == (0, 2, 3, 1)
    assert versioning.parse_version("0.1.1", legacy=True) == (0, 1, 1, 0)
    with pytest.raises(versioning.VersioningError, match="cuatro números"):
        versioning.parse_version("0.2.0")


def test_nothing_to_release_without_user_facing_commits(repo):
    commit(repo, "packages/janelkit/src/janelkit/a.py", "interno: mueve cosas")
    commit(repo, "docs/guia.md", "docs: guía")
    assert plan(repo) == {}


def test_menor_bumps_the_fourth_number_and_mayor_the_third(repo):
    commit(repo, "packages/janelkit/src/janelkit/a.py", "menor: corrige algo")
    assert plan(repo) == {"janelkit": "0.2.0.1"}
    commit(repo, "packages/janelkit/src/janelkit/b.py", "mayor: API nueva")
    commit(repo, "packages/janelkit/src/janelkit/c.py", "menor: otra corrección")
    assert plan(repo) == {"janelkit": "0.2.1.0"}  # mayor: gana; una versión por publicación, no una por commit


def test_each_package_has_its_own_mayor_and_menor(repo):
    commit(repo, "packages/janelkit-desktop/src/janelkit_desktop/tray.py", "mayor: bandeja")
    commit(repo, "packages/janelkit/src/janelkit/a.py", "menor: corrige algo")
    commit(repo, "docs/x.md", "menor: algo fuera de los paquetes")
    assert plan(repo) == {"janelkit": "0.2.0.1", "janelkit-desktop": "0.2.1.0"}


def test_counts_from_the_last_tag(repo):
    commit(repo, "packages/janelkit/src/janelkit/a.py", "mayor: API nueva")
    write_version(repo, "janelkit", "0.2.1.0", "version: janelkit 0.2.1.0")
    run(repo, "tag", "janelkit-v0.2.1.0")
    commit(repo, "packages/janelkit/src/janelkit/b.py", "menor: corrige")
    core = next(p for p in versioning.collect(repo) if p.name == "janelkit")
    assert core.released == (0, 2, 1, 0) and [s for _, s in core.commits] == ["corrige"]
    assert plan(repo) == {"janelkit": "0.2.1.1"}


def test_a_new_series_moves_every_package_and_its_range(repo):
    commit(repo, "packages/janelkit/src/janelkit/a.py", "mayor: paradigma nuevo")
    assert versioning.start_series(repo, "0.3") == {"janelkit": (0, 3, 0, 0), "janelkit-desktop": (0, 3, 0, 0)}
    assert 'version = "0.3.0.0"' in read(repo, "packages/janelkit-desktop/pyproject.toml")
    assert '"janelkit>=0.3,<0.4"' in read(repo, "packages/janelkit-desktop/pyproject.toml")
    assert '__version__ = "0.3.0.0"' in read(repo, "packages/janelkit/src/janelkit/__init__.py")
    run(repo, "commit", "-q", "-am", "interno: serie 0.3")
    # janelkit-desktop no tiene cambios propios, pero sale con la serie.
    assert plan(repo) == {"janelkit": "0.3.0.0", "janelkit-desktop": "0.3.0.0"}
    # Publicada la serie, cada paquete sigue por su cuenta.
    run(repo, "tag", "janelkit-v0.3.0.0")
    run(repo, "tag", "janelkit-desktop-v0.3.0.0")
    commit(repo, "packages/janelkit/src/janelkit/b.py", "menor: corrige")
    assert plan(repo) == {"janelkit": "0.3.0.1"}


def test_the_new_series_has_to_come_after_the_published_one(repo):
    with pytest.raises(versioning.VersioningError, match="no es posterior a la ya publicada"):
        versioning.start_series(repo, "0.2")


def test_every_package_shares_the_series(repo):
    write_version(repo, "janelkit", "0.3.0.0", "interno: solo el núcleo")
    with pytest.raises(versioning.VersioningError, match="no están en la misma serie.*series 0.3"):
        versioning.compute(repo)


@pytest.mark.parametrize("written, problem", [
    ("0.2.5.0", "Dentro de una serie la versión la calculan los commits"),
    ("0.3.1.0", "una serie nueva empieza en 0.3.0.0"),
    ("0.1.0.0", "por debajo de la última versión publicada"),
])
def test_by_hand_only_the_first_version_of_a_new_series(repo, written, problem):
    for name in ("janelkit", "janelkit-desktop"):
        write_version(repo, name, written)
    run(repo, "commit", "-q", "-am", "interno: versión a mano")
    with pytest.raises(versioning.VersioningError, match=problem):
        versioning.compute(repo)


def test_a_package_never_published_starts_with_the_series(repo):
    make_package(repo, "janelkit-store", "0.2.0.0", '"janelkit>=0.2,<0.3"')
    commit(repo, "packages/janelkit-store/src/janelkit_store/a.py", "mayor: paquete janelkit-store")
    assert plan(repo) == {"janelkit-store": "0.2.0.0"}
    write_version(repo, "janelkit-store", "0.2.1.0", "interno: a mano")
    with pytest.raises(versioning.VersioningError, match="su primera publicación empieza en 0.2.0.0"):
        versioning.compute(repo)


def test_an_extension_asks_for_exactly_its_series(repo):
    path = repo / "packages" / "janelkit-desktop" / "pyproject.toml"
    path.write_text(read(repo, "packages/janelkit-desktop/pyproject.toml").replace(">=0.2,<0.3", ">=0.1,<0.3"), encoding="utf-8")
    run(repo, "commit", "-q", "-am", "menor: rango")
    with pytest.raises(versioning.VersioningError, match=r"janelkit-desktop pide janelkit>=0.1,<0.3; .* janelkit>=0.2,<0.3"):
        versioning.compute(repo)


def test_apply_writes_versions_and_changelogs(repo):
    commit(repo, "packages/janelkit-desktop/src/janelkit_desktop/tray.py", "mayor: bandeja del sistema")
    commit(repo, "packages/janelkit-desktop/src/janelkit_desktop/clip.py", "menor: el portapapeles no se vaciaba")
    commit(repo, "packages/janelkit/src/janelkit/a.py", "menor: corrige timeout")
    assert {n: versioning.show(v) for n, v in versioning.apply(repo, today="2026-11-05").items()} == {
        "janelkit": "0.2.0.1", "janelkit-desktop": "0.2.1.0"}
    assert 'version = "0.2.1.0"' in read(repo, "packages/janelkit-desktop/pyproject.toml")
    assert '__version__ = "0.2.1.0"' in read(repo, "packages/janelkit-desktop/src/janelkit_desktop/__init__.py")
    readme = read(repo, "packages/janelkit-desktop/README.md")
    assert readme.index("### 0.2.1.0 (2026-11-05)") < readme.index("### 0.2.0.0")
    assert "#### Nuevo y cambios\n\n- bandeja del sistema" in readme
    assert "#### Corregido\n\n- el portapapeles no se vaciaba" in readme
    changes = read(repo, "docs/cambios.md")
    assert changes.index("## 0.2.0.1 (2026-11-05)") < changes.index("## 0.2.0.0")
    assert "### Corregido\n\n- corrige timeout" in changes


def test_apply_dates_a_section_written_by_hand(repo):
    path = repo / "docs" / "cambios.md"
    path.write_text(read(repo, "docs/cambios.md").replace("## 0.2.0.0", "## 0.2.0.1 (sin publicar)\n\n- A mano.\n\n## 0.2.0.0"), encoding="utf-8")
    commit(repo, "packages/janelkit/src/janelkit/a.py", "menor: corrige timeout")
    versioning.apply(repo, today="2026-11-05")
    changes = read(repo, "docs/cambios.md")
    assert "## 0.2.0.1 (2026-11-05)\n\n- A mano." in changes and "corrige timeout" not in changes
    assert "## 0.2.0.0\n" in changes  # la anterior no se toca, aunque empiece igual


def test_apply_publishes_a_new_series(repo):
    path = repo / "docs" / "cambios.md"
    path.write_text(read(repo, "docs/cambios.md").replace("## 0.2.0.0", "## 0.3.0.0 (sin publicar)\n\n- Paradigma.\n\n## 0.2.0.0"),
                    encoding="utf-8")
    commit(repo, "packages/janelkit/src/janelkit/a.py", "mayor: paradigma nuevo")
    versioning.start_series(repo, "0.3")
    run(repo, "commit", "-q", "-am", "interno: serie 0.3")  # toca todos los paquetes: no va a sus registros
    versioning.apply(repo, today="2026-11-05")
    assert "## 0.3.0.0 (2026-11-05)\n\n- Paradigma." in read(repo, "docs/cambios.md")
    assert "### 0.3.0.0 (2026-11-05)\n\n- Serie 0.3, sin cambios propios: va con `janelkit` 0.3." in read(
        repo, "packages/janelkit-desktop/README.md")


def test_check_range_reports_commits_without_prefix(repo):
    start = run(repo, "rev-parse", "HEAD").strip()
    commit(repo, "a.txt", "menor: bien")
    commit(repo, "b.txt", "Sin prefijo")
    assert versioning.check_range(repo, f"{start}..HEAD") == [
        f"el commit «Sin prefijo» no empieza por un prefijo válido: {versioning.VALID}"]
