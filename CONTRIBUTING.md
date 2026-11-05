# Contribuir a JanelKit

Los issues con un ejemplo mínimo (un `.janel` y lo que esperabas ver) son la forma más rápida de que algo se arregle. Para proponer un cambio grande, abre antes un issue y lo hablamos.

## Preparar el entorno

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
python -m pip install -r requirements-dev.txt   # los paquetes editables y las herramientas, con versiones probadas
git config core.hooksPath .githooks             # una vez: comprueba el prefijo de cada commit
```

## Comprobar un cambio

```bash
python -m pytest                 # toda la suite (Qt en modo offscreen); o un paquete: python -m pytest packages/janelkit
python tools/check_wheel.py      # construye wheel/sdist, instala en un venv limpio y prueba janel new + python main.py
python tools/versioning.py plan  # qué versión tocaría publicar y por qué
```

## Organización del repositorio

Un solo repositorio con el núcleo y los paquetes del ecosistema, que se publican por separado:

| Carpeta | Paquete | Qué es |
|---|---|---|
| [`packages/janelkit`](packages/janelkit/README.md) | `janelkit` | El núcleo: lenguaje `.janel`, compilador, reactividad, runtime, disposición, controles, ventanas, temas, tareas, vídeo, `janelkit.inspect` y el comando `janel`. |
| [`packages/janelkit-router`](packages/janelkit-router/README.md) | `janelkit-router` | Navegación entre pantallas: pilas de páginas y secciones (`pages`, `sections`, `<Pages>`, `<Sections>`). |
| [`packages/janelkit-store`](packages/janelkit-store/README.md) | `janelkit-store` | Datos compartidos: stores con acciones, escritura controlada y seguimiento de cambios, una instancia por aplicación; `persisted`. |
| [`packages/janelkit-i18n`](packages/janelkit-i18n/README.md) | `janelkit-i18n` | Traducciones (`t`, `i18n`): catálogos, plurales y formatos según el idioma. |
| [`packages/janelkit-desktop`](packages/janelkit-desktop/README.md) | `janelkit-desktop` | Servicios del sistema: diálogos nativos (archivos, carpeta, mensaje, confirmación) y portapapeles (`dialogs`, `clipboard`). |
| [`packages/janelkit-vscode`](packages/janelkit-vscode/README.md) | — | Resaltado de `.janel` para VS Code. |
| [`apps/examples`](apps/examples/README.md) | — | Ejemplos pequeños, uno por tema. |
| `apps/challenges` | — | Aplicaciones grandes que ponen a prueba el framework (chat, gestor, hoja, kanban, panel). |

Las extensiones solo usan la API pública del núcleo (`tests/test_boundaries.py` lo comprueba), y el núcleo no las importa. Qué va en cada sitio y cómo llega un `.janel` a la pantalla: [docs/arquitectura.md](docs/arquitectura.md).

## Commits y versiones

Cada commit empieza por `mayor:`, `menor:`, `interno:` o `docs:`: de ahí salen los dos últimos números de la versión de cada paquete (0.2.**#**.**#**), que calcula y publica la CI. La serie (0.**#**.0.0) es la misma para todos los paquetes y se cambia a mano con `python tools/versioning.py series` ([cómo se calcula](docs/arquitectura.md#versiones-y-publicación)).

Lo que es API pública y lo que puede cambiar entre versiones: [docs/api.md](docs/api.md).
