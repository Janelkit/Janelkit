"""Versiones a partir de los prefijos de los commits.

Una versión tiene cuatro números, E.S.M.m (por ejemplo 0.2.3.1):

    #.0.0.0  estable: la 1.0.0.0, cuando el uso y la comunidad lo digan          → a mano (series)
    0.#.0.0  serie: un cambio fuerte de arquitectura o de paradigma que rompe,
             como el paso de 0.1 a 0.2                                           → a mano (series)
    0.0.#.0  mayor:  API pública nueva, algo que se rompe o se retira, un cambio
                     de comportamiento                                           → commits
    0.0.0.#  menor:  corrige o mejora sin añadir ni quitar API (errores,
                     rendimiento, mensajes)                                      → commits

Los demás prefijos no suben nada: `interno:` (reorganización, pruebas, CI, herramientas),
`docs:` (solo documentación) y `version:` (reservado al workflow que publica).

La serie (E.S) es una sola para todos los paquetes de `packages/` y dice con qué núcleo
funciona cada uno: janelkit-desktop 0.2.x.x va con janelkit 0.2.x.x. Al cambiarla, todos
los paquetes pasan a E.S.0.0, también los que no tienen cambios, y cada extensión pide
`janelkit>=E.S,<E.(S+1)`. Se cambia con `series E.S`, y el workflow publica esa versión
tal cual.

Dentro de una serie, los dos últimos números son de cada paquete: un commit cuenta para los
paquetes cuyos archivos toca, desde la última etiqueta del paquete (`janelkit-v0.2.1.0`), y
`mayor:` gana a `menor:`. Un paquete que nunca se publicó (sin etiqueta) sale con la
primera versión de la serie, E.S.0.0.

Uso:
    python tools/versioning.py check RANGO          # commits de RANGO (p. ej. origin/main..HEAD) con prefijo válido
    python tools/versioning.py check-message ARCHIVO # para el hook commit-msg
    python tools/versioning.py plan                 # qué versión toca a cada paquete y por qué (no escribe)
    python tools/versioning.py apply                # escribe versiones y cambios; imprime "paquete versión" por línea
    python tools/versioning.py series E.S           # pasa todos los paquetes a la serie E.S (versiones y rangos)
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
RELEASING = ("mayor", "menor")  # mayor: → 0.0.#.0, menor: → 0.0.0.#; la serie se cambia a mano
VALID = "mayor:, menor:, interno:, docs: (version: es del workflow)"

Version = tuple[int, int, int, int]
Series = tuple[int, int]


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


# -- versiones -------------------------------------------------------------------
def parse_version(text: str, legacy: bool = False) -> Version:
    """E.S.M.m. Con `legacy`, también los tres números de antes (0.1.1 → 0.1.1.0)."""
    if re.fullmatch(r"\d+(?:\.\d+){2,3}" if legacy else r"\d+(?:\.\d+){3}", text) is None:
        raise VersioningError(f"versión no válida: {text!r} (se esperan cuatro números, E.S.M.m: 0.2.0.0)")
    parts = [int(p) for p in text.split(".")]
    return tuple(parts + [0] * (4 - len(parts)))  # type: ignore[return-value]


def show(version: tuple[int, ...]) -> str:
    return ".".join(map(str, version))


def series_of(version: Version) -> Series:
    return version[0], version[1]


def series_range(series: Series) -> str:
    """El rango del núcleo que pide una extensión de la serie: janelkit>=0.2,<0.3."""
    return f">={show(series)},<{series[0]}.{series[1] + 1}"


# -- paquetes --------------------------------------------------------------------
@dataclass
class Package:
    folder: Path  # relativa a la raíz
    name: str
    version: Version  # la del pyproject.toml
    released: Version | None = None  # la de su última etiqueta; None si nunca se publicó
    commits: list[tuple[str, str]] = field(default_factory=list)  # (prefijo, asunto sin prefijo)

    @property
    def tag_prefix(self) -> str:
        return f"{self.name}-v"

    @property
    def starts_series(self) -> bool:
        """Su versión es la primera de una serie que aún no publicó (o nunca publicó nada)."""
        return self.released is None or series_of(self.version) != series_of(self.released)

    def next_version(self) -> Version | None:
        written = show(self.version)
        major, series, mayor, menor = self.version
        if self.released is not None and series_of(self.version) < series_of(self.released):
            raise VersioningError(
                f"{self.name}: el pyproject.toml dice {written}, por debajo de la última versión publicada "
                f"({show(self.released)})")
        if self.starts_series:
            if (mayor, menor) != (0, 0):
                why = "su primera publicación" if self.released is None else "una serie nueva"
                raise VersioningError(f"{self.name}: {why} empieza en {major}.{series}.0.0, no en {written}")
            return self.version
        if self.version != self.released:
            raise VersioningError(
                f"{self.name}: el pyproject.toml dice {written} y la última etiqueta, {show(self.released)}. Dentro "
                "de una serie la versión la calculan los commits: deja la de la etiqueta (para cambiar de serie: "
                "python tools/versioning.py series E.S)")
        kinds = {kind for kind, _ in self.commits}
        if "mayor" in kinds:
            return (major, series, mayor + 1, 0)
        if "menor" in kinds:
            return (major, series, mayor, menor + 1)
        return None


def _pyproject_field(text: str, key: str) -> str:
    section = re.search(r"^\[project\]\n(.*?)(?=^\[|\Z)", text, re.M | re.S)
    match = re.search(rf'^{key} = "([^"]+)"', section[1] if section else "", re.M)
    if match is None:
        raise VersioningError(f"falta {key} en [project]")
    return match[1]


def packages(root: Path, legacy: bool = False) -> list[Package]:
    found = []
    for pyproject in sorted((root / "packages").glob("*/pyproject.toml")):
        text = pyproject.read_text(encoding="utf-8")
        name = _pyproject_field(text, "name")
        try:
            version = parse_version(_pyproject_field(text, "version"), legacy)
        except VersioningError as exc:
            raise VersioningError(f"{name}: {exc}") from None
        found.append(Package(pyproject.parent.relative_to(root), name, version))
    return found


def last_tag(root: Path, package: Package) -> tuple[Version, str] | None:
    """(versión, etiqueta) de la última versión publicada del paquete en la historia de HEAD."""
    tags = git(root, "tag", "--list", f"{package.tag_prefix}*", "--merged", "HEAD").split()
    versions = []
    for tag in tags:
        rest = tag[len(package.tag_prefix):]
        if re.fullmatch(r"\d+(?:\.\d+){2,3}", rest):  # las de antes tenían tres números
            versions.append((parse_version(rest, legacy=True), tag))
    return max(versions) if versions else None


def collect(root: Path) -> list[Package]:
    """Los paquetes con los commits que cuentan para cada uno desde su última etiqueta."""
    result = packages(root)
    for package in result:
        found = last_tag(root, package)
        package.released = found[0] if found else None
        revisions = f"{found[1]}..HEAD" if found else "HEAD"
        log = git(root, "log", "--no-merges", "--format=%s", revisions, "--", package.folder.as_posix())
        for subject in reversed(log.splitlines()):  # del más antiguo al más reciente
            match = PREFIX.match(subject)
            if match is not None and match[1] in RELEASING:
                package.commits.append((match[1], subject[len(match[1]) + 1:].strip()))
    return result


# -- comprobaciones antes de escribir -------------------------------------------
def shared_series(all_packages: list[Package]) -> Series:
    """La serie de todos los paquetes; error si no es la misma."""
    found = {series_of(p.version) for p in all_packages}
    if len(found) != 1:
        detail = ", ".join(f"{p.name} {show(series_of(p.version))}" for p in all_packages)
        newest = show(max(found))
        raise VersioningError(
            f"los paquetes no están en la misma serie ({detail}). La serie es una sola para todos: "
            f"python tools/versioning.py series {newest}")
    return found.pop()


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


def check_ranges(root: Path, all_packages: list[Package], series: Series) -> None:
    """Cada extensión pide exactamente la serie del núcleo en la que está."""
    from packaging.specifiers import SpecifierSet

    expected = series_range(series)
    wrong = [(name, spec) for name, spec in _core_ranges(root, all_packages) if SpecifierSet(spec) != SpecifierSet(expected)]
    if wrong:
        detail = ", ".join(f"{name} pide janelkit{spec}" for name, spec in wrong)
        raise VersioningError(
            f"{detail}; en la serie {show(series)} cada extensión pide janelkit{expected} "
            f"(python tools/versioning.py series {show(series)} lo escribe)")


def compute(root: Path) -> tuple[list[Package], dict[str, Version]]:
    all_packages = collect(root)
    series = shared_series(all_packages)
    plan = {p.name: v for p in all_packages if (v := p.next_version()) is not None}
    check_ranges(root, all_packages, series)
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


def _write_version(root: Path, package: Package, version: str) -> None:
    _replace_once(root / package.folder / "pyproject.toml", r'^version = "[^"]+"', f'version = "{version}"')
    _replace_once(_module_init(root, package), r'^__version__ = "[^"]+"', f'__version__ = "{version}"')


def _changelog(root: Path, package: Package) -> tuple[Path, str]:
    """Archivo de cambios y nivel de título de cada versión en él."""
    if package.name == "janelkit":
        return root / "docs" / "cambios.md", "##"
    return root / package.folder / "README.md", "###"


def write_changelog(path: Path, level: str, version: str, commits: list[tuple[str, str]], today: str) -> None:
    """Fecha la sección de la versión si ya existe (escrita a mano); si no, la crea con los commits."""
    text = path.read_text(encoding="utf-8")
    heading = re.compile(rf"^{re.escape(level)} {re.escape(version)}(?![\d.])(.*)$", re.M)
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
    if len(parts) == 2:  # una serie nueva sin commits propios
        series = show(series_of(parse_version(version)))
        parts += [f"- Serie {series}, sin cambios propios: va con `janelkit` {series}.", ""]
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


def apply(root: Path, today: str | None = None) -> dict[str, Version]:
    all_packages, plan = compute(root)
    today = today or datetime.date.today().isoformat()
    for package in all_packages:
        new = plan.get(package.name)
        if new is None:
            continue
        _write_version(root, package, show(new))
        path, level = _changelog(root, package)
        write_changelog(path, level, show(new), package.commits, today)
    return plan


def start_series(root: Path, text: str) -> dict[str, Version]:
    """Pasa todos los paquetes a E.S.0.0 y cada extensión a janelkit>=E.S,<E.(S+1)."""
    match = re.fullmatch(r"(\d+)\.(\d+)", text)
    if match is None:
        raise VersioningError(f"serie no válida: {text!r} (se espera E.S, p. ej. 0.3)")
    series: Series = (int(match[1]), int(match[2]))
    all_packages = packages(root, legacy=True)
    published = [(series_of(found[0]), p.name) for p in all_packages if (found := last_tag(root, p)) is not None]
    if published and series <= max(published)[0]:
        raise VersioningError(
            f"la serie {show(series)} no es posterior a la ya publicada ({show(max(published)[0])}, {max(published)[1]})")
    version = show((*series, 0, 0))
    for package in all_packages:
        _write_version(root, package, version)
        if package.name != "janelkit":
            _replace_once(root / package.folder / "pyproject.toml", r'"janelkit\s*[<>=!~][^"]*"', f'"janelkit{series_range(series)}"')
    return {p.name: (*series, 0, 0) for p in all_packages}


# -- línea de órdenes ------------------------------------------------------------
def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):  # la consola de Windows no es UTF-8 por defecto
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
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
                if new is None:
                    target = f"{show(package.version)} (sin cambios)"
                elif package.released is None:
                    target = f"{show(new)} (primera publicación)"
                else:
                    target = f"{show(package.released)} → {show(new)}" + (" (serie nueva)" if package.starts_series else "")
                print(f"{package.name}: {target}")
                for kind, subject in package.commits:
                    print(f"    {kind}: {subject}")
            return 0
        if command == "apply":
            for name, version in apply(root).items():
                print(f"{name} {show(version)}")
            return 0
        if command == "series" and len(args) == 1:
            for name, version in start_series(root, args[0]).items():
                print(f"{name} {show(version)}")
            return 0
    except VersioningError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
