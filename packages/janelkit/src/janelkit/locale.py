"""Idioma de la interfaz: dirección de escritura y formatos de los controles de Qt.

    from janelkit import locale

    locale.set("ar")      # la interfaz se refleja (derecha a izquierda)
    locale.rtl            # True

Es reactivo: al cambiarlo, todas las ventanas se reflejan o dejan de reflejarse y Qt
usa el idioma nuevo como `QLocale` por defecto. Las traducciones (`t`, catálogos,
formatos de número y fecha) no son del núcleo: las da `janelkit_i18n`, que cambia este
idioma al llamar a `i18n.set()`.
"""
from __future__ import annotations

from .reactivity import State

RTL_LANGUAGES = {"ar", "he", "fa", "ur", "yi", "ps", "sd", "ug", "dv"}
DEFAULT = "es"


class Locale:
    """Idioma activo de la interfaz (código como "es", "en-US" o "ar")."""

    def __init__(self) -> None:
        self._language = State(DEFAULT)

    @property
    def language(self) -> str:
        return self._language.value

    @property
    def rtl(self) -> bool:
        """True si el idioma activo se escribe de derecha a izquierda (la interfaz se refleja)."""
        return self.language.split("-")[0].split("_")[0] in RTL_LANGUAGES

    def set(self, language: str) -> None:
        self._language.value = language

    def reset(self) -> None:
        self._language.value = DEFAULT

    def __repr__(self) -> str:
        return f"<locale {self._language.peek()!r}>"


locale = Locale()
