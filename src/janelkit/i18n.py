"""Traducciones y formatos según el idioma, con cambio de idioma en caliente.

    from pathlib import Path
    from janelkit import i18n, t

    i18n.load(Path(__file__).parent / "locales")   # locales/es.json, locales/en.json…
    i18n.set("es")

En la plantilla: `<Text>{t("saludo", nombre=nombre)}</Text>`. Como `t` lee el
idioma actual, al llamar a `i18n.set("en")` se actualiza todo lo que traduce.

Catálogo (JSON): `{"saludo": "Hola, {nombre}", "tareas": {"one": "{n} tarea", "other": "{n} tareas"}}`.
Los plurales se eligen con el parámetro `n`. Si falta una clave, se usa el idioma
por defecto y, si tampoco está, la propia clave (con un aviso en el logger `janelkit`).
"""
from __future__ import annotations

import json
import logging
from datetime import date as Date, datetime
from pathlib import Path
from typing import Any

from .reactivity import State

log = logging.getLogger("janelkit")
RTL_LANGUAGES = {"ar", "he", "fa", "ur", "yi", "ps", "sd", "ug", "dv"}


class I18nError(ValueError):
    pass


class I18n:
    """Idioma activo, catálogos de traducción y formatos (número, fecha, moneda)."""

    def __init__(self) -> None:
        self._catalogs: dict[str, dict[str, Any]] = {}
        self._language = State("es")
        self.default = "es"  # idioma de reserva para claves que faltan
        self._revision = State(0)
        self._warned: set[tuple[str, str]] = set()

    # -- idioma -------------------------------------------------------------------
    @property
    def language(self) -> str:
        return self._language.value

    @property
    def languages(self) -> list[str]:
        self._revision.value
        return sorted(self._catalogs)

    @property
    def rtl(self) -> bool:
        """True si el idioma activo se escribe de derecha a izquierda (la interfaz se refleja)."""
        return self.language.split("-")[0].split("_")[0] in RTL_LANGUAGES

    def set(self, language: str) -> None:
        if self._catalogs and language not in self._catalogs:
            raise I18nError(f"idioma sin catálogo: {language!r}; disponibles: {', '.join(sorted(self._catalogs))}")
        self._language.value = language

    # -- catálogos ----------------------------------------------------------------
    def add(self, language: str, entries: dict[str, Any]) -> None:
        """Añade (o completa) el catálogo de `language`."""
        self._catalogs.setdefault(language, {}).update(entries)
        self._revision.update(lambda r: r + 1)

    def load(self, folder: str | Path) -> None:
        """Carga `<idioma>.json` de `folder` (p. ej. es.json, en.json, ar.json)."""
        folder = Path(folder)
        files = sorted(folder.glob("*.json"))
        if not files:
            raise I18nError(f"no hay catálogos .json en {folder}")
        for file in files:
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise I18nError(f"{file}: JSON no válido: {exc}") from None
            if not isinstance(data, dict):
                raise I18nError(f"{file}: el catálogo debe ser un objeto {{clave: texto}}")
            self.add(file.stem, data)

    def reset(self) -> None:
        self._catalogs.clear()
        self.default = "es"
        self._language.value = "es"
        self._warned.clear()
        self._revision.update(lambda r: r + 1)

    # -- traducción -----------------------------------------------------------------
    def translate(self, key: str, **params: Any) -> str:
        language = self.language
        self._revision.value
        entry = self._lookup(language, key)
        if entry is None and language != self.default:
            entry = self._lookup(self.default, key)
        if entry is None:
            if (language, key) not in self._warned:
                self._warned.add((language, key))
                log.warning("i18n: falta la traducción de %r en %r", key, language)
            return key
        if isinstance(entry, dict):  # plurales
            n = params.get("n", params.get("count"))
            form = "zero" if n == 0 and "zero" in entry else "one" if n == 1 and "one" in entry else "other"
            entry = entry.get(form, next(iter(entry.values())))
        try:
            return str(entry).format(**params)
        except (KeyError, IndexError, ValueError) as exc:
            log.warning("i18n: %r en %r necesita el parámetro %s", key, language, exc)
            return str(entry)

    def _lookup(self, language: str, key: str) -> Any:
        catalog = self._catalogs.get(language)
        if catalog is None and "-" in language:  # "es-MX" -> "es"
            catalog = self._catalogs.get(language.split("-")[0])
        return None if catalog is None else catalog.get(key)

    # -- formatos (QLocale) -------------------------------------------------------------
    def _locale(self) -> Any:
        from PySide6.QtCore import QLocale

        return QLocale(self.language.replace("-", "_"))

    def number(self, value: float, decimals: int | None = None) -> str:
        """1234.5 -> "1.234,5" (es) / "1,234.5" (en)."""
        locale = self._locale()
        if decimals is None:
            return locale.toString(value) if isinstance(value, int) else locale.toString(float(value), "g", 12)
        return locale.toString(float(value), "f", decimals)

    def currency(self, value: float, symbol: str = "") -> str:
        """Importe al estilo del idioma; `symbol` ("€", "US$", "EUR"…) sustituye al de la región del idioma."""
        locale = self._locale()
        return locale.toCurrencyString(float(value), symbol) if symbol else locale.toCurrencyString(float(value))

    def date(self, value: Date | datetime, style: str = "short") -> str:
        """Fecha (y hora, si es un datetime) en formato "short" o "long" del idioma."""
        from PySide6.QtCore import QDate, QLocale, QTime

        locale = self._locale()
        fmt = QLocale.FormatType.LongFormat if style == "long" else QLocale.FormatType.ShortFormat
        day = locale.toString(QDate(value.year, value.month, value.day), fmt)
        if isinstance(value, datetime):  # la hora, siempre en formato corto (sin zona horaria)
            hour = locale.toString(QTime(value.hour, value.minute), QLocale.FormatType.ShortFormat)
            return f"{day} {hour}"
        return day

    def __repr__(self) -> str:
        return f"<i18n {self._language.peek()!r} de {sorted(self._catalogs)}>"


i18n = I18n()


def t(key: str, **params: Any) -> str:
    """Traduce `key` al idioma activo. Reactivo: en la plantilla se actualiza al cambiar de idioma."""
    return i18n.translate(key, **params)
