from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from system_core.core.jobs import JobContext
from system_core.core.manifest import Operation
from system_core.core.paths import ensure_project_dirs, get_project_paths
from system_core.services import yandex_portable_service as service


UTF16_INI = (
    "; Chrome++ configuration\n"
    "[general]\n"
    "data_dir=%app%\\..\\Data\n"
    "cache_dir=%app%\\..\\Cache\n"
    "command_line=\n"
    "launch_on_startup=\n"
    "launch_on_exit=\n"
    "[tabs]\n"
    "double_click_close=1\n"
)


def _context(tmp_path: Path, **parameters: object) -> JobContext:
    paths = get_project_paths(tmp_path)
    ensure_project_dirs(paths)
    return JobContext(
        paths=paths,
        operation=Operation(
            id="test",
            title="Test",
            description="",
            service="system_core.services.yandex_portable_service:build_portable",
            parameters=dict(parameters),
        ),
        log_file=paths.logs / "test.log",
        report_dir=paths.report,
    )


def _build_with_ini(tmp_path: Path, encoding: str = "utf-16-le", bom: bytes = b"\xff\xfe") -> Path:
    build = tmp_path / service.PORTABLE_NAME
    (build / "App").mkdir(parents=True)
    (build / "App" / "chrome++.ini").write_bytes(bom + UTF16_INI.encode(encoding))
    return build


def test_configure_ini_keeps_the_utf16_file_readable(tmp_path: Path) -> None:
    """Chrome++ ships the ini as UTF-16 LE; rewriting it as UTF-8 kills it silently."""
    build = _build_with_ini(tmp_path)

    service._configure_chrome_plus_ini(_context(tmp_path), build, wipe_registry=True)

    raw = (build / "App" / "chrome++.ini").read_bytes()
    assert raw.startswith(b"\xff\xfe")
    text = raw[2:].decode("utf-16-le")
    assert f'launch_on_exit=reg delete "{service.YANDEX_REGISTRY_BRANCH}" /f;' in text
    assert "data_dir=%app%\\..\\Data" in text
    assert "double_click_close=1" in text


def test_configure_ini_leaves_the_hook_empty_when_not_asked(tmp_path: Path) -> None:
    build = _build_with_ini(tmp_path)

    service._configure_chrome_plus_ini(_context(tmp_path), build, wipe_registry=False)

    text = (build / "App" / "chrome++.ini").read_bytes()[2:].decode("utf-16-le")
    assert "launch_on_exit=\n" in text
    assert "reg delete" not in text


def test_configure_ini_handles_a_plain_utf8_file(tmp_path: Path) -> None:
    build = _build_with_ini(tmp_path, encoding="utf-8", bom=b"")

    service._configure_chrome_plus_ini(_context(tmp_path), build, wipe_registry=True)

    raw = (build / "App" / "chrome++.ini").read_bytes()
    assert not raw.startswith(b"\xff\xfe")
    assert "reg delete" in raw.decode("utf-8")


def test_version_is_read_out_of_the_cdn_path() -> None:
    url = (
        "https://ext-cloudcdn.cdn.yandex.net/abc/browser/yandex/26_6_5_621_113843/ru/"
        "Yandex.exe?win10pin=1&hash=deadbeef"
    )

    assert service._version_from_cdn_url(url) == "26.6.5.621"


def test_version_is_empty_when_the_path_is_not_a_yandex_build() -> None:
    assert service._version_from_cdn_url("https://apps.apple.com/ru/app/yandex/id483693909") == ""


def test_a_release_tag_and_its_file_version_are_the_same_release() -> None:
    """Release `1.18.2` ships a file reporting `1.18.2.0`; that is not an update."""
    assert service.same_version("1.18.2", "1.18.2.0")
    assert service.same_version("26.6.5.621", "26.6.5.621")
    assert not service.same_version("1.18.2", "1.18.20")
    assert not service.same_version("26.6.5.621", "26.6.5.700")


def test_same_version_is_false_when_one_side_is_unknown() -> None:
    """An unreadable build must look outdated, never accidentally current."""
    assert not service.same_version("1.18.2", "")
    assert not service.same_version("", "")


def test_build_versions_falls_back_to_the_version_folder(tmp_path: Path) -> None:
    """A build handed over by someone else still names its own version."""
    build = tmp_path / service.PORTABLE_NAME
    (build / "App" / "26.6.5.621").mkdir(parents=True)
    (build / "App" / "25.10.1.100").mkdir(parents=True)

    assert service.build_versions(build).yandex == "26.6.5.621"


def test_disable_bundled_updater_removes_it(tmp_path: Path) -> None:
    build = tmp_path / service.PORTABLE_NAME
    version_dir = build / "App" / "26.6.5.621"
    version_dir.mkdir(parents=True)
    (version_dir / service.UPDATER_EXECUTABLE).write_bytes(b"MZ")
    (version_dir / "browser.dll").write_bytes(b"MZ")

    removed = service._disable_bundled_updater(_context(tmp_path), build)

    assert removed == [str(Path("App") / "26.6.5.621" / service.UPDATER_EXECUTABLE)]
    assert not (version_dir / service.UPDATER_EXECUTABLE).exists()
    assert (version_dir / "browser.dll").exists()


def test_github_assets_fall_back_to_the_release_page(monkeypatch: pytest.MonkeyPatch) -> None:
    """The API allows 60 anonymous calls an hour; the pages have no quota at all."""
    page = (
        '<a href="/Bush2021/chrome_plus/releases/download/1.18.2/Chrome%2B%2B_v1.18.2_x86_x64_arm64.7z">'
        "</a>"
    )

    class _Response:
        def __init__(self, url: str, body: bytes) -> None:
            self._url = url
            self._body = body

        def geturl(self) -> str:
            return self._url

        def read(self) -> bytes:
            return self._body

    @contextmanager
    def fake_urlopen(request, timeout=0):  # noqa: ANN001 - mirrors urlopen's shape
        url = request.full_url
        if "api.github.com" in url:
            raise RuntimeError("rate limit exceeded")
        if url.endswith("/releases/latest"):
            yield _Response("https://github.com/Bush2021/chrome_plus/releases/tag/1.18.2", b"")
            return
        yield _Response(url, page.encode("utf-8"))

    monkeypatch.setattr(service, "urlopen", fake_urlopen)

    tag, assets = service.github_latest_assets(service.CHROME_PLUS_REPO)

    assert tag == "1.18.2"
    assert assets == [
        (
            "Chrome%2B%2B_v1.18.2_x86_x64_arm64.7z",
            "https://github.com/Bush2021/chrome_plus/releases/download/1.18.2/"
            "Chrome%2B%2B_v1.18.2_x86_x64_arm64.7z",
        )
    ]


def test_launcher_points_at_the_browser(tmp_path: Path) -> None:
    build = tmp_path / service.PORTABLE_NAME
    build.mkdir(parents=True)

    launcher = service._write_launcher(_context(tmp_path), build)

    assert launcher.name == f"{service.PORTABLE_NAME}.cmd"
    assert f"App\\{service.BROWSER_EXECUTABLE}" in launcher.read_text(encoding="utf-8")


def test_read_guard_result_parses_status_and_detail(tmp_path: Path) -> None:
    """Guard status lines are 'STATUS\tdetail'; the reader renders them for the log."""
    result = tmp_path / "guard.result"
    result.write_text("ADDED\tE:/out", encoding="utf-8")
    assert service._read_guard_result(result) == "ADDED: E:/out"

    result.write_text("REMOVED", encoding="utf-8")
    assert service._read_guard_result(result) == "REMOVED"

    assert service._read_guard_result(tmp_path / "missing") == ""


def test_guard_path_argument_joins_with_a_pipe(tmp_path: Path) -> None:
    """Folders travel through ShellExecute as one '|'-joined argument; spaces stay."""
    joined = service._guard_path_argument([Path(r"E:\out"), Path(r"D:\build x\App")])
    assert joined == r"E:\out|D:\build x\App"
    assert joined.split("|") == [r"E:\out", r"D:\build x\App"]


def test_defender_guard_is_a_noop_when_defender_is_inactive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No Defender means no elevation: the guard must never reach for UAC."""
    context = _context(tmp_path)
    monkeypatch.setattr(service, "_defender_active", lambda _ctx: False)

    def fail_if_elevated(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("_defender_guard tried to elevate while Defender was inactive")

    monkeypatch.setattr(service, "_run_elevated_powershell", fail_if_elevated)

    entered = False
    with service._defender_guard(context, context.paths.output):
        entered = True
    assert entered
    assert not (context.paths.workspace / service._DEFENDER_GUARD_DIRNAME).exists()


def test_defender_guard_survives_a_declined_uac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A declined UAC (ShellExecute code 5) must not abort the build; it proceeds unguarded."""
    context = _context(tmp_path)
    monkeypatch.setattr(service, "_defender_active", lambda _ctx: True)
    monkeypatch.setattr(service, "_run_elevated_powershell", lambda _script, _args: 5)

    entered = False
    with service._defender_guard(context, [context.paths.output, context.paths.input]):
        entered = True
    assert entered

    leftovers = list((context.paths.workspace / service._DEFENDER_GUARD_DIRNAME).glob("*"))
    assert leftovers == []
