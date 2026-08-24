from __future__ import annotations

import os
import socket
import subprocess

import pytest

from system_core.ui_nicegui import app as gui_app
from system_core.ui_nicegui import window


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_gui_host_guard_accepts_loopback_and_rejects_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AUDION_ALLOW_REMOTE_GUI", raising=False)

    gui_app.assert_gui_host_allowed("127.0.0.1")
    window.assert_gui_host_allowed("::1")
    with pytest.raises(SystemExit, match="Refusing non-loopback host"):
        gui_app.assert_gui_host_allowed("0.0.0.0")
    with pytest.raises(SystemExit, match="Refusing non-loopback host"):
        window.assert_gui_host_allowed("192.168.1.10")


def test_remote_host_requires_explicit_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUDION_ALLOW_REMOTE_GUI", "1")

    gui_app.assert_gui_host_allowed("0.0.0.0")
    window.assert_gui_host_allowed("192.168.1.10")


def test_picker_supervisor_refuses_a_second_dialog() -> None:
    assert gui_app._PICKER_RUN_LOCK.acquire(blocking=False)
    try:
        with pytest.raises(RuntimeError, match="already open"):
            gui_app.run_picker_script("", "not reached")
    finally:
        gui_app._PICKER_RUN_LOCK.release()


def test_active_project_paths_follow_workbench_routes(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source.txt"
    target = tmp_path / "target"
    source.write_text("payload", encoding="utf-8")
    target.mkdir()
    monkeypatch.setitem(gui_app.state, "source_path", str(source))
    monkeypatch.setitem(gui_app.state, "destination_path", str(target))

    active = gui_app.active_project_paths()

    assert active.input == source
    assert active.output == target


@pytest.mark.skipif(os.name != "nt", reason="Windows hidden-process contract")
def test_window_server_process_is_hidden_and_stops_as_a_tree() -> None:
    assert window.hidden_subprocess_flags() == int(subprocess.CREATE_NO_WINDOW)
    port = _free_loopback_port()
    server = window.start_server("127.0.0.1", port)
    try:
        assert server is not None
        assert window.wait_for_server("127.0.0.1", port, timeout=20.0)
        assert window.GUI_PID_FILE.read_text(encoding="utf-8").strip() == str(server.pid)
    finally:
        window.stop_server(server)

    assert server is not None and server.poll() is not None
    assert not window.GUI_PID_FILE.exists()
    assert not window.port_is_open("127.0.0.1", port)
