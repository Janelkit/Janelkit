"""Versiones a partir de los prefijos de los commits.

Cada commit empieza por un prefijo que dice qué nota quien usa JanelKit:

    mayor:    API pública nueva, algo que se rompe o se retira, un cambio de comportamiento  → 0.#.0
    menor:    corrige o mejora sin añadir ni quitar API (errores, rendimiento, mensajes)    → 0.0.#
    interno:  reorganización, pruebas, CI, herramientas: el usuario no lo nota              → nada
    docs:     solo documentación                                                            → nada
    version:  reservado al workflow que publica las versiones                               → nada

Cada paquete de `packages/` con `pyproject.toml` tiene su versión y su etiqueta
(`janelkit-v0.2.0`, `janelkit-desktop-v0.1.1`). Un commit cuenta para los paquetes cuyos
archivos toca. Se miran los commits desde la última etiqueta del paquete: `mayor:` gana a
`menor:`. La 1.0.0 nunca se calcula sola: se decide a mano.

Uso:
    python tools/versioning.py check RANGO          # commits de RANGO (p. ej. origin/main..HEAD) con prefijo válido
    python tools/versioning.py check-message ARCHIVO # para el hook commit-msg
    python tools/versioning.py plan                 # qué versión toca a cada paquete y por qué (no escribe)
    python tools/versioning.py apply                # escribe versiones y cambios; imprime "paquete versión" por línea
"""
from __future__ import annotations

import datetime
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PREFIX = re.compile(r"^(mayor|menor|interno|docs|version): \S")
EXEMPT = re.compile(r"^(Merge |Revert \"|fixup! |squash! )")
BUMPS = {"mayor": "minor", "menor": "patch"}
VALID = "mayor:, menor:, interno:, docs: (version: es del workflow)"


class VersioningError(RuntimeError):
    pass


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout


# -- comprobar prefijos ----------------------------------------------------------
def message_problem(subject: str) -> str | None:
    """None si el asunto del commit es válido; si no, el motivo."""
    if EXEMPT.match(subject) or PREFIX.match(subject):
        return None
    return f"el commit «{subject}» no empieza por un prefijo válido: {VALID}"


def check_range(root: Path, revisions: str) -> list[str]:
    subjects = git(root, "log", "--format=%s", revisions).splitlines()
    return [p for p in map(message_problem, subjects) if p]


# -- paquetes y versiones --------------------------------------------------------
@dataclass
class Package:
    folder: Path  # relativa a la raíz
    name: str
    version: tuple[int, int, int]
    commits: list[tuple[str, str]] = field(default_factory=list)  # (prefijo, asunto sin prefijo)

    @property
    def tag_prefix(self) -> str:
        return f"{self.name}-v"

    def next_version(self) -> tuple[int, int, int] | None:
        kinds = {kind for kind, _ in self.commits}
        major, minor, patch = self.version
        if "mayor" in kinds:
            return (major, minor + 1, 0)
        if "menor" in kinds:
            return (major, minor, patch + 1)
        return None


def parse_version(text: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", text)
    if match is None:
        raise VersioningError(f"versión no válida: {text!r} (se espera X.Y.Z)")
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def show(version: tuple[int, int, int]) -> str:
    return ".".join(map(str, version))


def _pyproject_field(text: str, key: str) -> str:
    section = re.search(r"^\[project\]\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
    match = re.search(rf'^{key} = "([^"]+)"', section[1] if section else "", re.M)
    if match is None:
        raise VersioningError(f"falta {key} en [project]")
    return match[1]


def packages(root: Path) -> list[Package]:
    found = []
    for pyproject in sorted((root / "packages").glob("*/pyproject.toml")):
        text = pyproject.read_text(encoding="utf-8")
        found.append(Package(pyproject.parent.relative_to(root), _pyproject_field(text, "name"),
                             parse_version(_pyproject_field(text, "version"))))
    return found


def last_tag(root: Path, package: Package) -> str:
    tags = git(root, "tag", "--list", f"{package.tag_prefix}*", "--merged", "HEAD").split()
    versions = []
    for tag in tags:
        rest = tag[len(package.tag_prefix):]
        if re.fullmatch(r"\d+\.\d+\.\d+", rest):
            versions.append((parse_version(rest), tag))
    if not versions:
        raise VersioningError(
            f"{package.name}: no hay ninguna etiqueta {package.tag_prefix}X.Y.Z en la historia: "
            f"crea la de partida (git tag {package.tag_prefix}{show(package.version)} <commit>)"
        )
    return max(versions)[1]


def collect(root: Path) -> list[Package]:
    """Los paquetes con los commits que cuentan para cada uno desde su última etiqueta."""
    result = packages(root)
    for package in result:
        log = git(root, "log", "--no-merges", "--format=%s", f"{last_tag(root, package)}..HEAD", "--", package.folder.as_posix())
        for subject in reversed(log.splitlines()):  # del más antiguo al más reciente
            match = PREFIX.match(subject)
            if match is not None and match[1] in BUMPS:
                package.commits.append((match[1], subject[len(match[1]) + 1:].strip()))
    return result


# -- comprobaciones antes de escribir -------------------------------------------
def _core_ranges(root: Path, all_packages: list[Package]) -> list[tuple[str, str]]:
    """(extensión, especificador) de cada extensión que depende de `janelkit`."""
    out = []
    for package in all_packages:
        if package.name == "janelkit":
            continue
        text = (root / package.folder / "pyproject.toml").read_text(encoding="utf-8")
        for requirement in re.findall(r'"janelkit\s*([<>=!~][^"]*)"', text):
            out.append((package.name, requirement.strip()))
    return out


def check_compatibility(root: Path, all_packages: list[Package], plan: dict[str, tuple[int, int, int]]) -> None:
    core = plan.get("janelkit")
    if core is None:
        return
    from packaging.specifiers import SpecifierSet

    broken = [(name, spec) for name, spec in _core_ranges(root, all_packages) if show(core) not in SpecifierSet(spec)]
    if broken:
        detail = ", ".join(f"{name} pide janelkit{spec}" for name, spec in broken)
        raise VersioningError(
            f"janelkit pasaría a {show(core)}, pero {detail}. Amplía el rango en un commit «menor:» "
            "de esas extensiones (si de verdad son compatibles) antes de publicar."
        )


def compute(root: Path) -> tuple[list[Package], dict[str, tuple[int, int, int]]]:
    all_packages = collect(root)
    plan = {p.name: v for p in all_packages if (v := p.next_version()) is not None}
    check_compatibility(root, all_packages, plan)
    return all_packages, plan


# -- escribir --------------------------------------------------------------------
def _replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    new, count = re.subn(pattern, replacement, text, count=1, flags=re.M)
    if count != 1:
        raise VersioningError(f"{path}: no se encontró {pattern!r}")
    path.write_text(new, encoding="utf-8", newline="")


def _module_init(root: Path, package: Package) -> Path:
    inits = [p for p in (root / package.folder / "src").glob("*/__init__.py") if "__version__ =" in p.read_text(encoding="utf-8")]
    if len(inits) != 1:
        raise VersioningError(f"{package.name}: se esperaba un __init__.py con __version__ en src/")
    return inits[0]


def _changelog(root: Path, package: Package) -> tuple[Path, str]:
    """Archivo de cambios y nivel de título de cada versión en él."""
    if package.name == "janelkit":
        return root / "docs" / "cambios.md", "##"
    return root / package.folder / "README.md", "###"


def write_changelog(path: Path, level: str, version: str, commits: list[tuple[str, str]], today: str) -> None:
    """Fecha la sección de la versión si ya existe (escrita a mano); si no, la crea con los commits."""
    text = path.read_text(encoding="utf-8")
    heading = re.compile(rf"^{re.escape(level)} {re.escape(version)}\b(.*)$", re.M)
    existing = heading.search(text)
    if existing is not None:
        text = text[: existing.start()] + f"{level} {version} ({today})" + text[existing.end():]
        path.write_text(text, encoding="utf-8", newline="")
        return
    parts = [f"{level} {version} ({today})", ""]
    sub = level + "#"
    for kind, title in (("mayor", "Nuevo y cambios"), ("menor", "Corregido")):
        items = [subject for k, subject in commits if k == kind]
        if items:
            parts += [f"{sub} {title}", "", *(f"- {s}" for s in items), ""]
    section = "\n".join(parts) + "\n"
    if level == "##":
        first = re.search(r"^## ", text, re.M)
        at = first.start() if first else len(text)
    else:
        changes = re.search(r"^## Cambios\s*\n\n?", text, re.M)
        if changes is None:
            raise VersioningError(f"{path}: falta la sección «## Cambios»")
        at = changes.end()
    path.write_text(text[:at] + section + text[at:], encoding="utf-8", newline="")


def apply(root: Path, today: str | None = None) -> dict[str, tuple[int, int, int]]:
    all_packages, plan = compute(root)
    today = today or datetime.date.today().isoformat()
    for package in all_packages:
        new = plan.get(package.name)
        if new is None:
            continue
        version = show(new)
        _replace_once(root / package.folder / "pyproject.toml", r'^version = "[^"]+"', f'version = "{version}"')
        _replace_once(_module_init(root, package), r'^__version__ = "[^"]+"', f'__version__ = "{version}"')
        path, level = _changelog(root, package)
        write_changelog(path, level, version, package.commits, today)
    return plan


# -- línea de órdenes ------------------------------------------------------------
def main(argv: list[str]) -> int:
    root = Path(git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
    command, *args = argv or ["plan"]
    try:
        if command == "check":
            problems = check_range(root, args[0])
            for problem in problems:
                print(problem, file=sys.stderr)
            return 1 if problems else 0
        if command == "check-message":
            subject = Path(args[0]).read_text(encoding="utf-8").splitlines()[0] if args else ""
            problem = message_problem(subject)
            if problem:
                print(problem, file=sys.stderr)
            return 1 if problem else 0
        if command == "plan":
            all_packages, plan = compute(root)
            for package in all_packages:
                new = plan.get(package.name)
                target = f"{show(package.version)} → {show(new)}" if new else f"{show(package.version)} (sin cambios)"
                print(f"{package.name}: {target}")
                for kind, subject in package.commits:
                    print(f"    {kind}: {subject}")
            return 0
        if command == "apply":
            for name, version in apply(root).items():
                print(f"{name} {show(version)}")
            return 0
    except VersioningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
