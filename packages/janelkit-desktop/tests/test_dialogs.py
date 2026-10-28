"""Diálogos nativos (janelkit_desktop.dialogs), también respondidos desde janelkit.inspect."""
import asyncio

from PySide6.QtCore import QMetaObject, QUrl, Q_ARG

from janelkit.inspect import mount as mount_app
from janelkit_desktop import dialogs


def test_open_file_dialog_returns_the_selected_path(janel_app, mount, tmp_path):
    mount("<Text>x</Text>")
    target = tmp_path / "nota.txt"
    target.write_text("x", encoding="utf-8")  # FileDialog solo acepta archivos que existen

    async def scenario():
        task = asyncio.ensure_future(dialogs.open_file("Abrir", filters=["Texto (*.txt)"], folder=tmp_path))
        await asyncio.sleep(0.05)
        (dialog,) = dialogs.pending()
        assert dialog.property("title") == "Abrir" and dialog.property("nameFilters") == ["Texto (*.txt)"]
        dialog.setProperty("selectedFile", QUrl.fromLocalFile(str(target)))
        QMetaObject.invokeMethod(dialog, "done", Q_ARG(int, 1))  # como si el usuario aceptara
        return await task

    assert janel_app.run_until(scenario()) == target
    assert dialogs.pending() == []


def test_cancelled_dialogs_return_none_or_false(janel_app, mount):
    mount("<Text>x</Text>")

    async def cancel_next(coro):
        task = asyncio.ensure_future(coro)
        await asyncio.sleep(0.05)
        QMetaObject.invokeMethod(dialogs.pending()[0], "reject")
        return await task

    assert janel_app.run_until(cancel_next(dialogs.save_file(name="a.txt"))) is None
    assert janel_app.run_until(cancel_next(dialogs.choose_folder())) is None
    assert janel_app.run_until(cancel_next(dialogs.confirm("¿Seguro?"))) is False
    assert janel_app.run_until(cancel_next(dialogs.open_files())) == []


def test_confirm_accepts(janel_app, mount):
    mount("<Text>x</Text>")

    async def scenario():
        task = asyncio.ensure_future(dialogs.confirm("¿Borrar?", title="Notas"))
        await asyncio.sleep(0.05)
        dialog = dialogs.pending()[0]
        assert dialog.property("text") == "¿Borrar?"
        QMetaObject.invokeMethod(dialog, "done", Q_ARG(int, 0x400))  # botón Aceptar
        return await task

    assert janel_app.run_until(scenario()) is True


def test_inspect_answers_a_file_dialog(tmp_path):
    app_file = tmp_path / "App.janel"
    app_file.write_text(
        """<script>
from janelkit import state
from janelkit_desktop import dialogs
chosen = state(None)

async def pick():
    chosen.value = await dialogs.open_file()
</script>
<Column><Button on:click={pick}>Abrir</Button></Column>
""",
        encoding="utf-8",
    )
    target = tmp_path / "a.txt"
    target.write_text("x", encoding="utf-8")
    with mount_app(app_file) as app:
        app.find(text="Abrir").click()
        app.wait(0.02)
        assert len(app.dialogs()) == 1
        app.answer_dialog(target)
        assert app.get("chosen") == target


def test_answer_dialog_accepts_or_cancels_a_confirm(tmp_path):
    app_file = tmp_path / "App.janel"
    app_file.write_text(
        """<script lang="python">
from janelkit import state
from janelkit_desktop import dialogs
answers = state([])

async def ask():
    answers.value = answers.value + [await dialogs.confirm("¿Seguro?")]
</script>
<Window><Button text="Preguntar" on:click={ask()} /></Window>
""",
        encoding="utf-8",
    )
    with mount_app(app_file) as app:
        for result in (True, False):
            app.find(text="Preguntar").click()
            app.wait(0.02)
            app.answer_dialog(result)
        assert list(app.get("answers")) == [True, False]
