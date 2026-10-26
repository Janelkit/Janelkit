"""Punto de entrada del comando `flux`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .. import __version__
from ..diagnostics import FluxError


def _cmd_new(args: argparse.Namespace) -> int:
    from .scaffolding import ScaffoldError, create_project

    try:
        result = create_project(args.name, Path(args.path) if args.path else None)
    except ScaffoldError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        shown = result.root.relative_to(Path.cwd())
    except ValueError:
        shown = result.root
    print(f"Proyecto creado en {shown}\n")
    for f in result.files:
        print(f"  {f.relative_to(result.root).as_posix()}")
    print("\nSiguientes pasos:")
    print(f"  cd {shown}")
    print("  python main.py")
    print("\nUsa el mismo entorno de Python en el que instalaste FluxUI.")
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    from ..compiler import parse_file
    from ..compiler.ast_nodes import dump

    try:
        print(dump(parse_file(args.file)))
    except FluxError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


def _cmd_compile(args: argparse.Namespace) -> int:
    from ..compiler import compile_file

    try:
        compiled = compile_file(args.file)
    except FluxError as exc:
        print(exc, file=sys.stderr)
        return 1
    for warning in compiled.warnings:
        print(warning.format(), file=sys.stderr)
    if args.output:
        Path(args.output).write_text(compiled.qml, encoding="utf-8")
    else:
        sys.stdout.write(compiled.qml)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flux",
        description="Herramientas de FluxUI: componentes .flux para escritorio con Python y Qt Quick.",
    )
    parser.add_argument("--version", action="version", version=f"FluxUI {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<comando>")

    p_new = sub.add_parser("new", help="crea un proyecto nuevo con main.py y src/App.flux")
    p_new.add_argument("name", help="nombre del proyecto (también el nombre de la carpeta)")
    p_new.add_argument("--path", help="carpeta donde crear el proyecto (por defecto, la actual)")
    p_new.set_defaults(func=_cmd_new)

    p_parse = sub.add_parser("parse", help="muestra el AST de un archivo .flux o sus errores")
    p_parse.add_argument("file")
    p_parse.set_defaults(func=_cmd_parse)

    p_compile = sub.add_parser("compile", help="muestra el QML generado para un archivo .flux")
    p_compile.add_argument("file")
    p_compile.add_argument("-o", "--output", help="escribe el QML en este archivo")
    p_compile.set_defaults(func=_cmd_compile)
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        # Consolas de Windows con codificación heredada: no fallar por acentos.
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
