"""Búsqueda de libros en Open Library (https://openlibrary.org/developers/api).

Es código síncrono y bloqueante, como el de muchas bibliotecas: la interfaz
lo ejecuta en otro hilo con `await background(search, consulta)`.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

API = "https://openlibrary.org/search.json"


def search(query: str, limit: int = 15) -> list[dict]:
    params = urllib.parse.urlencode(
        {"q": query, "limit": limit, "fields": "key,title,author_name,first_publish_year"}
    )
    request = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": "JanelKit-ejemplo/0.1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.load(response)
    return [
        {
            "key": doc["key"],
            "title": doc.get("title") or "(sin título)",
            "author": ", ".join(doc.get("author_name", [])[:2]) or "Autor desconocido",
            "year": doc.get("first_publish_year"),
        }
        for doc in data.get("docs", [])
    ]
