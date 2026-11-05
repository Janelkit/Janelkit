"""La sesión de aplicación (janelkit.ext.session): una por run() y por cada inspect.mount()."""
from janelkit import ext
from janelkit.inspect import mount


def test_each_mount_has_its_own_session_with_a_temporary_data_folder(tmp_path, monkeypatch):
    monkeypatch.delenv("JANELKIT_DATA_DIR", raising=False)
    (tmp_path / "App.janel").write_text("<window><text>hola</text></window>", encoding="utf-8")
    ended = []
    with mount(tmp_path / "App.janel"):
        first = ext.session()
        assert first is not None and not first.ended
        assert first.data_dir.name.startswith("janelkit-data-") and first.data_dir.is_dir()
        first.data["mi_paquete"] = 1
        first.on_end(lambda: ended.append("primera"))
    assert ended == ["primera"] and first.ended and ext.session() is None
    assert not first.data_dir.exists()  # la carpeta temporal se borra al desmontar
    with mount(tmp_path / "App.janel"):
        second = ext.session()
        assert second is not first and "mi_paquete" not in second.data


def test_the_data_folder_follows_janelkit_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("JANELKIT_DATA_DIR", str(tmp_path / "datos"))
    (tmp_path / "App.janel").write_text("<window />", encoding="utf-8")
    with mount(tmp_path / "App.janel"):
        assert ext.session().data_dir == tmp_path / "datos"


def test_an_error_in_one_end_callback_does_not_stop_the_others(tmp_path, caplog):
    (tmp_path / "App.janel").write_text("<window />", encoding="utf-8")
    ended = []
    with mount(tmp_path / "App.janel"):
        s = ext.session()
        s.on_end(lambda: ended.append("a"))
        s.on_end(lambda: 1 / 0)
    assert ended == ["a"] and "error al terminar la sesión" in caplog.text


def test_an_ext_scope_owns_what_is_created_inside_it():
    from janelkit import effect, interval, state

    n, seen = state(0), []
    scope = ext.Scope()
    with scope.active():
        effect(lambda: seen.append(n.value))
        timer = interval(1000, lambda: None)
    n.value = 1
    scope.dispose()
    n.value = 2
    assert seen == [0, 1] and scope.disposed and not timer.active
