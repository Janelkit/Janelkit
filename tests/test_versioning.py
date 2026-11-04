"""Versiones calculadas a partir de los prefijos de los commits (tools/versioning.py)."""
from __future__ import annotations

import importlib.util
import os
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


def run(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, env=ENV).stdout


def make_package(root: Path, folder: str, name: str, version: str, module: str, deps: str = "") -> None:
    base = root / "packages" / folder
    (base / "src" / module).mkdir(parents=True)
    (base / "pyproject.toml").write_text(
        f'[project]\nname = "{name}"\nversion = "{version}"\ndependencies = [{deps}]\n\n[build-system]\n', encoding="utf-8"
    )
    (base / "src" / module / "__init__.py").write_text(f'"""m"""\n__version__ = "{version}"\n', encoding="utf-8")
    (base / "README.md").write_text(f"# {name}\n\n## Cambios\n\n### {version}\n\n- Primera.\n\n## Licencia\n", encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    run(tmp_path, "init", "-q", "-b", "main")
    make_package(tmp_path, "janelkit", "janelkit", "0.1.1", "janelkit")
    make_package(tmp_path, "janelkit-desktop", "janelkit-desktop", "0.1.0", "janelkit_desktop", '"janelkit>=0.1,<0.2"')
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "cambios.md").write_text("# Cambios\n\nIntro.\n\n## 0.1.1\n\n- Antes.\n", encoding="utf-8")
    run(tmp_path, "add", "-A")
    run(tmp_path, "commit", "-q", "-m", "interno: inicio")
    run(tmp_path, "tag", "janelkit-v0.1.1")
    run(tmp_path, "tag", "janelkit-desktop-v0.1.0")
    return tmp_path


def commit(root: Path, path: str, message: str) -> None:
    file = root / path
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(file.read_text(encoding="utf-8") + "x\n" if file.exists() else "x\n", encoding="utf-8")
    run(root, "add", "-A")
    run(root, "commit", "-q", "-m", message)


def plan(root: Path) -> dict[str, str]:
    return {name: versioning.show(v) for name, v in versioning.compute(root)[1].items()}


@pytest.mark.parametrize("subject, ok", [
    ("mayor: Window con screen", True),
    ("menor: corrige timeout", True),
    ("interno: prueba de capas", True),
    ("docs: guía", True),
    ("version: janelkit 0.2.0", True),
    ("Merge branch 'main'", True),
    ("Añade cosas", False),
    ("mayor:sin espacio", False),
    ("feat: algo", False),
])
def test_commit_prefixes(subject, ok):
    assert (versioning.message_problem(subject) is None) is ok


def test_nothing_to_release_without_user_facing_commits(repo):
    commit(repo, "packages/janelkit/src/janelkit/a.py", "interno: mueve cosas")
    commit(repo, "docs/guia.md", "docs: guía")
    assert plan(repo) == {}


def test_menor_bumps_patch_and_mayor_wins(repo):
    commit(repo, "packages/janelkit/src/janelkit/a.py", "menor: corrige algo")
    assert plan(repo) == {"janelkit": "0.1.2"}
    # Antes de una 0.2 del núcleo, las extensiones amplían su rango (si son compatibles).
    pyproject = repo / "packages" / "janelkit-desktop" / "pyproject.toml"
    pyproject.write_text(pyproject.read_text(encoding="utf-8").replace("<0.2", "<0.3"), encoding="utf-8")
    run(repo, "commit", "-q", "-am", "menor: compatible con janelkit 0.2")
    commit(repo, "packages/janelkit/src/janelkit/b.py", "mayor: API nueva")
    commit(repo, "packages/janelkit/src/janelkit/c.py", "menor: otra corrección")
    assert plan(repo) == {"janelkit": "0.2.0", "janelkit-desktop": "0.1.1"}


def test_each_package_counts_only_the_commits_that_touch_it(repo):
    commit(repo, "packages/janelkit-desktop/src/janelkit_desktop/tray.py", "mayor: bandeja")
    commit(repo, "docs/x.md", "menor: algo fuera de los paquetes")
    assert plan(repo) == {"janelkit-desktop": "0.2.0"}


def test_counts_from_the_last_tag(repo):
    commit(repo, "packages/janelkit/src/janelkit/a.py", "mayor: API nueva")
    run(repo, "tag", "janelkit-v0.2.0")
    commit(repo, "packages/janelkit/src/janelkit/b.py", "menor: corrige")
    # La versión del pyproject es la que se sube (0.1.1 → 0.1.2 aquí, porque el fixture no la cambió):
    # en el repositorio real, apply la habría dejado en 0.2.0.
    assert [s for _, s in versioning.collect(repo)[0].commits] == ["corrige"]


def test_a_core_bump_outside_the_extensions_range_is_refused(repo):
    commit(repo, "packages/janelkit/src/janelkit/a.py", "mayor: API nueva")
    with pytest.raises(versioning.VersioningError, match="janelkit-desktop pide janelkit>=0.1,<0.2"):
        versioning.compute(repo)


def test_missing_start_tag_is_an_error(repo):
    run(repo, "tag", "-d", "janelkit-desktop-v0.1.0")
    with pytest.raises(versioning.VersioningError, match="git tag janelkit-desktop-v0.1.0"):
        versioning.compute(repo)


def test_apply_writes_versions_and_changelogs(repo):
    commit(repo, "packages/janelkit-desktop/src/janelkit_desktop/tray.py", "mayor: bandeja del sistema")
    commit(repo, "packages/janelkit-desktop/src/janelkit_desktop/clip.py", "menor: el portapapeles no se vaciaba")
    commit(repo, "packages/janelkit/src/janelkit/a.py", "menor: corrige timeout")
    assert {n: versioning.show(v) for n, v in versioning.apply(repo, today="2026-11-05").items()} == {
        "janelkit": "0.1.2", "janelkit-desktop": "0.2.0"}
    desktop = repo / "packages" / "janelkit-desktop"
    assert 'version = "0.2.0"' in (desktop / "pyproject.toml").read_text(encoding="utf-8")
    assert '__version__ = "0.2.0"' in (desktop / "src" / "janelkit_desktop" / "__init__.py").read_text(encoding="utf-8")
    readme = (desktop / "README.md").read_text(encoding="utf-8")
    assert readme.index("### 0.2.0 (2026-11-05)") < readme.index("### 0.1.0")
    assert "#### Nuevo y cambios\n\n- bandeja del sistema" in readme
    assert "#### Corregido\n\n- el portapapeles no se vaciaba" in readme
    changes = (repo / "docs" / "cambios.md").read_text(encoding="utf-8")
    assert changes.index("## 0.1.2 (2026-11-05)") < changes.index("## 0.1.1")
    assert "### Corregido\n\n- corrige timeout" in changes


def test_apply_dates_a_section_written_by_hand(repo):
    path = repo / "docs" / "cambios.md"
    path.write_text(path.read_text(encoding="utf-8").replace("## 0.1.1", "## 0.1.2 (sin publicar)\n\n- A mano.\n\n## 0.1.1"), encoding="utf-8")
    commit(repo, "packages/janelkit/src/janelkit/a.py", "menor: corrige timeout")
    versioning.apply(repo, today="2026-11-05")
    changes = path.read_text(encoding="utf-8")
    assert "## 0.1.2 (2026-11-05)\n\n- A mano." in changes and "corrige timeout" not in changes


def test_check_range_reports_commits_without_prefix(repo):
    start = run(repo, "rev-parse", "HEAD").strip()
    commit(repo, "a.txt", "menor: bien")
    commit(repo, "b.txt", "Sin prefijo")
    assert versioning.check_range(repo, f"{start}..HEAD") == [
        f"el commit «Sin prefijo» no empieza por un prefijo válido: {versioning.VALID}"]
