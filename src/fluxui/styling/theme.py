"""Temas: conjuntos de tokens (colores, radios, tipografía, espacios) intercambiables en caliente.

Los estilos usan los tokens con `var(--nombre)`; los controles base de FluxUI
también los usan, de modo que cambiar de tema actualiza toda la interfaz:

    from fluxui import theme
    theme.set("dark")          # o theme.toggle()
    theme.extend("light", brand="#7048e8")    # añade o cambia tokens
    theme.define("sepia", base="light", bg="#f4ecd8", text="#433422")

`theme.name` y `theme.tokens` son reactivos: se pueden usar en `@computed`
y en la plantilla (`{theme.name}`).
"""
from __future__ import annotations

import re
from typing import Any

from ..reactivity import State

_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")

_SIZES: dict[str, Any] = {
    "radius_sm": 4,
    "radius": 8,
    "radius_lg": 14,
    "font_family": "",  # vacío: fuente del sistema
    "font_size_sm": 12,
    "font_size": 14,
    "font_size_lg": 18,
    "font_size_xl": 24,
    "space_1": 4,
    "space_2": 8,
    "space_3": 12,
    "space_4": 16,
    "space_5": 24,
    "space_6": 32,
}

LIGHT: dict[str, Any] = {
    "bg": "#f5f6f8",
    "surface": "#ffffff",
    "surface_alt": "#eef0f4",
    "text": "#1b1f24",
    "text_muted": "#626b78",
    "border": "#d5dae1",
    "primary": "#3b5bdb",
    "on_primary": "#ffffff",
    "danger": "#e03131",
    "on_danger": "#ffffff",
    "success": "#2b8a3e",
    "warning": "#e8590c",
    "hover": "#10000000",  # capa que se mezcla con el fondo al pasar el ratón (#AARRGGBB)
    "pressed": "#24000000",
    **_SIZES,
}

DARK: dict[str, Any] = {
    "bg": "#14161a",
    "surface": "#1e2127",
    "surface_alt": "#272b33",
    "text": "#e6e8ec",
    "text_muted": "#99a1ad",
    "border": "#373c46",
    "primary": "#7b93ff",
    "on_primary": "#0d1330",
    "danger": "#ff6b6b",
    "on_danger": "#1f0606",
    "success": "#51cf66",
    "warning": "#ffa94d",
    "hover": "#1affffff",
    "pressed": "#33ffffff",
    **_SIZES,
}


class ThemeError(ValueError):
    pass


def _check_tokens(tokens: dict[str, Any]) -> dict[str, Any]:
    for key, value in tokens.items():
        if not _KEY_RE.match(key):
            raise ThemeError(f"nombre de token no válido: {key!r} (usa minúsculas y _; en CSS: var(--{key.replace('_', '-')}))")
        if not isinstance(value, (str, int, float)) or isinstance(value, bool):
            raise ThemeError(f"el token {key!r} debe ser texto o número, no {type(value).__name__}")
    return tokens


class Theme:
    """Registro de temas y tema activo. Hay una instancia global: `fluxui.theme`."""

    def __init__(self) -> None:
        self._themes: dict[str, dict[str, Any]] = {"light": dict(LIGHT), "dark": dict(DARK)}
        self._name = State("light")
        self._revision = State(0)  # cambia cuando se modifican tokens

    @property
    def name(self) -> str:
        return self._name.value

    @property
    def names(self) -> list[str]:
        self._revision.value
        return list(self._themes)

    @property
    def tokens(self) -> dict[str, Any]:
        """Tokens del tema activo (lectura reactiva)."""
        name = self._name.value
        self._revision.value
        return dict(self._themes[name])

    def tokens_of(self, name: str) -> dict[str, Any]:
        """Tokens de un tema concreto (reactivo), sin que sea el activo."""
        self._revision.value
        if name not in self._themes:
            raise ThemeError(f"tema desconocido {name!r}; disponibles: {', '.join(self._themes)}")
        return dict(self._themes[name])

    def token(self, key: str) -> Any:
        return self.tokens[key]

    def set(self, name: str) -> None:
        if name not in self._themes:
            raise ThemeError(f"tema desconocido {name!r}; disponibles: {', '.join(self._themes)}")
        self._name.value = name

    def toggle(self) -> None:
        """Alterna entre claro y oscuro."""
        self.set("light" if self._name.peek() == "dark" else "dark")

    def define(self, name: str, base: str = "light", **tokens: Any) -> None:
        """Crea (o reemplaza) un tema a partir de otro."""
        if base not in self._themes:
            raise ThemeError(f"tema base desconocido {base!r}")
        self._themes[name] = {**self._themes[base], **_check_tokens(tokens)}
        self._revision.update(lambda r: r + 1)

    def extend(self, name: str | None = None, **tokens: Any) -> None:
        """Añade o cambia tokens de un tema, o de todos si no se indica `name`."""
        _check_tokens(tokens)
        targets = [name] if name is not None else list(self._themes)
        for target in targets:
            if target not in self._themes:
                raise ThemeError(f"tema desconocido {target!r}")
            self._themes[target].update(tokens)
        self._revision.update(lambda r: r + 1)

    def reset(self) -> None:
        """Vuelve a los temas de fábrica (útil en pruebas)."""
        self._themes = {"light": dict(LIGHT), "dark": dict(DARK)}
        self._name.value = "light"
        self._revision.update(lambda r: r + 1)

    def __repr__(self) -> str:
        return f"<Theme {self._name.peek()!r} de {list(self._themes)}>"


theme = Theme()
