# Rendimiento medido

Tiempos indicativos (Windows 11, plataforma `offscreen`), para saber qué esperar y detectar regresiones. Cada tabla dice cómo reproducirla.

## Listas

Windows 11, offscreen, lista de filas con casilla, texto y botón. Se reproduce con `python tools/bench.py`:

| Operación | 100 filas | 1000 filas |
|---|---|---|
| Crear la lista completa | 38 ms | 430 ms |
| Insertar una fila en medio (reasignando) | 1 ms | 7 ms |
| Insertar una fila en medio (`insert`) | 1 ms | 5 ms |
| Añadir al final (`append`) | 1 ms | 2 ms |
| Editar una fila (reasignando) | <1 ms | 3 ms |
| Editar una fila en el sitio (`todo["done"] = True`) | <1 ms | <1 ms |
| Invertir el orden (`reverse`) | 2 ms | 93 ms |
| Vaciar (`clear`) | 2 ms | 39 ms |

Modificar en el sitio un elemento de una colección reactiva solo actualiza los bindings que leyeron ese elemento.

Con `<List>` (virtualizada: solo se crean las filas visibles):

| Operación | 1000 filas | 10 000 filas |
|---|---|---|
| Crear la lista completa | 9 ms | 39 ms |
| Insertar una fila en medio (`insert`) | 2 ms | 16 ms |
| Editar una fila en el sitio | <1 ms | <1 ms |
| Invertir el orden | 11 ms | 25 ms |
| Vaciar | 1 ms | 3 ms |

En `<Scroll>` las filas se crean todas; para miles de elementos, usa `<List>`.

## Arranque y respuesta de una aplicación

`python tools/bench_app.py`. Arranque en frío de cada ejemplo, offscreen:

| Ejemplo | Importar | Compilar | Qt + montar | Total |
|---|---|---|---|---|
| counter | 214 ms | 10 ms | 38 ms | 262 ms |
| todo | 238 ms | 4 ms | 51 ms | 293 ms |
| notes | 225 ms | 9 ms | 51 ms | 285 ms |
| books | 205 ms | 3 ms | 79 ms | 287 ms |
| files | 206 ms | 9 ms | 56 ms | 271 ms |

Casi todo el arranque es importar PySide6. Compilar cuesta menos de 10 ms, así que **no hace falta una caché de compilación** por ahora.

Explorador (`apps/examples/files`) sobre una carpeta de 5000 archivos:

| Operación | Tiempo |
|---|---|
| Listar la carpeta (hilo aparte + lista) | 62 ms |
| Filtrar (quedan 10) | 12 ms |
| Quitar el filtro (vuelven todos) | 31 ms |
| Ordenar por tamaño | 31 ms |
| Elegir un archivo | 3 ms |

## `<flex>` y rejillas

`python apps/examples/flex/bench.py`:

| Operación | Tiempo |
|---|---|
| Rejilla de 200 tarjetas (`apps/examples/flex`), por fotograma | 17 ms |
| 300 tarjetas en un `<Scroll>`, por paso al cambiar el ancho | 8,7 ms |
| Invertir 1000 filas en un `<Scroll>` | ~93 ms |

Dentro de una caja con el motor de `<flex>`, lo de dentro también lo usa; lo que queda con un layout de Qt se coloca al momento (ver [flex.md](flex.md#vía-rápida-layouts-de-qt)).

Lo medido para vídeo en tiempo real está en [vision.md](vision.md#mediciones-del-núcleo).
