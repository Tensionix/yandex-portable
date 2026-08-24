from __future__ import annotations

from pathlib import Path
import argparse
import ipaddress
import os
import socket
import subprocess
import sys
import time
import webbrowser


ROOT = Path(__file__).resolve().parents[2]
APP_PY = ROOT / "system_core" / "ui_nicegui" / "app.py"
GUI_PID_FILE = ROOT / "logs" / "gui_server.pid"
APP_ICON = ROOT / "system_core" / "icons" / "app.ico"


def get_window_icon() -> str | None:
    icon = Path(os.environ.get("AUDION_APP_ICON", str(APP_ICON)))
    return str(icon) if icon.exists() else None


def configure_windows_taskbar() -> None:
    if os.name != "nt":
        return
    app_id = os.environ.get("AUDION_APP_ID")
    if not app_id:
        clean = "".join(ch if ch.isalnum() else "." for ch in ROOT.name).strip(".")
        app_id = f"Audion.Tools.{clean or 'App'}"
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def load_ui_defaults() -> dict[str, object]:
    try:
        from system_core.core.config import load_yaml_or_json

        manifest = load_yaml_or_json(ROOT / "config" / "tool_manifest.yaml")
        ui_info = manifest.get("ui", {}) if isinstance(manifest, dict) else {}
        tool_info = manifest.get("tool", {}) if isinstance(manifest, dict) else {}
        return {
            "title": str(ui_info.get("title") or tool_info.get("name") or "Audion GUI"),
            "host": str(ui_info.get("host") or "127.0.0.1"),
            "port": int(ui_info.get("port") or 8080),
            "width": int(ui_info.get("width") or 1600),
            "height": int(ui_info.get("height") or 900),
            "min_width": int(ui_info.get("min_width") or 1180),
            "min_height": int(ui_info.get("min_height") or 720),
        }
    except Exception:
        return {
            "title": "Audion GUI",
            "host": "127.0.0.1",
            "port": 8080,
            "width": 1600,
            "height": 900,
            "min_width": 1180,
            "min_height": 720,
        }


UI_DEFAULTS = load_ui_defaults()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audion GUI window.")
    parser.add_argument("--host", default=str(UI_DEFAULTS["host"]))
    parser.add_argument("--port", type=int, default=int(UI_DEFAULTS["port"]))
    parser.add_argument("--browser", action="store_true", help="Open in the default browser instead of pywebview.")
    parser.add_argument("--gui", default="edgechromium", help="pywebview backend to use on Windows.")
    return parser.parse_args()


def port_is_open(host: str, port: int) -> bool:
    family = socket.AF_INET6 if ":" in str(host or "") else socket.AF_INET
    try:
        with socket.socket(family, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((host, port)) == 0
    except OSError:
        return False


def choose_port(host: str, preferred_port: int) -> int:
    port = preferred_port
    while port_is_open(host, port):
        port += 1
    return port


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def env_flag_enabled(name: str) -> bool:
    return str(os.environ.get(name, "")).strip().lower() in {"1", "true", "yes", "on"}


def assert_gui_host_allowed(host: str) -> None:
    normalized = str(host or "").strip().lower().strip("[]")
    try:
        is_loopback = normalized == "localhost" or ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        is_loopback = normalized == "localhost"
    if is_loopback or env_flag_enabled("AUDION_ALLOW_REMOTE_GUI"):
        return
    raise SystemExit(
        "Refusing non-loopback host for a GUI with process execution. "
        "Use 127.0.0.1/localhost/::1, or set AUDION_ALLOW_REMOTE_GUI=1 explicitly."
    )


def hidden_subprocess_flags() -> int:
    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW"):
        return int(subprocess.CREATE_NO_WINDOW)
    return 0


def hidden_subprocess_startupinfo() -> subprocess.STARTUPINFO | None:
    if os.name != "nt" or not hasattr(subprocess, "STARTUPINFO"):
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0
    return startupinfo


def kill_process_tree(pid: int) -> None:
    if pid <= 0 or not process_exists(pid):
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=hidden_subprocess_flags(),
            startupinfo=hidden_subprocess_startupinfo(),
        )
        return
    try:
        os.kill(pid, 15)
    except OSError:
        pass


def cleanup_previous_server() -> None:
    try:
        if not GUI_PID_FILE.exists():
            return
        pid = int(GUI_PID_FILE.read_text(encoding="utf-8").strip())
        kill_process_tree(pid)
        GUI_PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def wait_for_server(host: str, port: int, timeout: float = 20.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_open(host, port):
            return True
        time.sleep(0.2)
    return False


def start_server(host: str, port: int) -> subprocess.Popen[str] | None:
    logs = ROOT / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout = (logs / "gui_server_stdout.log").open("w", encoding="utf-8")
    stderr = (logs / "gui_server_stderr.log").open("w", encoding="utf-8")
    env = os.environ.copy()
    env.pop("PYTEST_CURRENT_TEST", None)
    env.pop("NICEGUI_SCREEN_TEST_PORT", None)
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("NO_COLOR", None)
    env["CLICOLOR"] = "1"
    env["CLICOLOR_FORCE"] = "1"
    env["FORCE_COLOR"] = "1"
    env["AUDION_GUI_TERMINAL"] = "1"
    try:
        server = subprocess.Popen(
            [sys.executable, "-u", str(APP_PY), "--host", host, "--port", str(port), "--no-browser"],
            cwd=str(ROOT),
            stdout=stdout,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            creationflags=hidden_subprocess_flags(),
            startupinfo=hidden_subprocess_startupinfo(),
        )
    finally:
        stdout.close()
        stderr.close()
    GUI_PID_FILE.write_text(str(server.pid), encoding="utf-8")
    return server


def stop_server(server: subprocess.Popen[str] | None) -> None:
    if server and server.poll() is None:
        kill_process_tree(server.pid)
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=2)
    GUI_PID_FILE.unlink(missing_ok=True)


def main() -> int:
    args = parse_args()
    assert_gui_host_allowed(args.host)
    os.environ.setdefault("PYWEBVIEW_LOG", "error")
    configure_windows_taskbar()
    cleanup_previous_server()
    port = choose_port(args.host, args.port)
    url = f"http://{args.host}:{port}/"
    server = start_server(args.host, port)

    if not wait_for_server(args.host, port):
        print(f"GUI server did not start: {url}")
        stop_server(server)
        return 1

    if args.browser:
        try:
            webbrowser.open(url)
            if server:
                print(f"GUI server is running: {url}")
                print("Close this console window to stop the server.")
                server.wait()
            return 0
        except KeyboardInterrupt:
            return 0
        finally:
            stop_server(server)

    try:
        import webview  # type: ignore
    except Exception as exc:
        print(f"pywebview is not available: {exc}")
        print(f"Browser fallback is available explicitly: {Path(__file__).name} --browser")
        stop_server(server)
        return 1

    try:
        webview.create_window(
            str(UI_DEFAULTS["title"]),
            url,
            width=int(UI_DEFAULTS["width"]),
            height=int(UI_DEFAULTS["height"]),
            min_size=(int(UI_DEFAULTS["min_width"]), int(UI_DEFAULTS["min_height"])),
        )
        webview.start(
            gui=args.gui,
            debug=False,
            private_mode=False,
            storage_path=str(ROOT / "._runtime" / "webview"),
            icon=get_window_icon(),
        )
        return 0
    except Exception as exc:
        print(f"pywebview failed: {exc}")
        print(f"Browser fallback is available explicitly: {Path(__file__).name} --browser")
        return 1
    finally:
        stop_server(server)


if __name__ == "__main__":
    raise SystemExit(main())
