from pathlib import Path

from fluxui import run

if __name__ == "__main__":
    raise SystemExit(run(Path(__file__).parent / "src" / "App.flux"))
