from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any
import ctypes
import re
import html
import locale
import os

try:
    from .output_decode import decode_process_bytes
except ImportError:  # imported as a top-level module rather than a package member
    from output_decode import decode_process_bytes  # type: ignore[no-redef]


SGR_FG = {
    30: "#111827",
    31: "#f87171",
    32: "#4ade80",
    33: "#facc15",
    34: "#60a5fa",
    35: "#c084fc",
    36: "#22d3ee",
    37: "#e5e7eb",
    90: "#6b7280",
    91: "#fca5a5",
    92: "#86efac",
    93: "#fde047",
    94: "#93c5fd",
    95: "#d8b4fe",
    96: "#67e8f9",
    97: "#f9fafb",
}

SGR_BG = {
    40: "#111827",
    41: "#7f1d1d",
    42: "#14532d",
    43: "#713f12",
    44: "#1e3a8a",
    45: "#581c87",
    46: "#164e63",
    47: "#f3f4f6",
    100: "#374151",
    101: "#991b1b",
    102: "#166534",
    103: "#854d0e",
    104: "#1d4ed8",
    105: "#7e22ce",
    106: "#0e7490",
    107: "#ffffff",
}

MOJIBAKE_PENALTY_CHARS = set("ЋЎўЈ¤ҐЄє©«»¬­®Її")

# A pipe can swallow the escape and leave the rest of an SGR sequence behind.
# "[36m" is noise; "[OK]" is text, and the final "m" is what tells them apart.
ORPHAN_SGR = re.compile(r"\[[0-9;]*m")


def _consume_escape(text: str, index: int) -> tuple[int, tuple[str, str, str] | None]:
    end = len(text)
    if index + 1 >= end:
        return index + 1, None

    marker = text[index + 1]
    if marker == "[":
        cursor = index + 2
        while cursor < end and not ("@" <= text[cursor] <= "~"):
            cursor += 1
        if cursor >= end:
            return end, None
        return cursor + 1, ("csi", text[index + 2 : cursor], text[cursor])

    if marker == "]":
        cursor = index + 2
        while cursor < end:
            if text[cursor] == "\x07":
                return cursor + 1, None
            if text[cursor] == "\x1b" and cursor + 1 < end and text[cursor + 1] == "\\":
                return cursor + 2, None
            cursor += 1
        return end, None

    return min(index + 2, end), None


def _is_control_char(char: str) -> bool:
    code = ord(char)
    if char in "\n\t":
        return False
    return code < 32 or code == 127 or 128 <= code <= 159


def _sgr_codes(payload: str) -> list[int] | None:
    if not payload:
        return [0]

    codes: list[int] = []
    for item in payload.split(";"):
        if not item:
            codes.append(0)
            continue
        if not item.isdigit():
            return None
        codes.append(int(item))
    return codes or [0]


def _xterm_256_color(index: int, *, background: bool) -> str | None:
    """The colour an xterm-256 index stands for.

    Indices 0-15 are the terminal's own scheme, so they come from this app's
    palette — that is what makes the window look like the rest of the app rather
    than like someone else's terminal. Everything above is standardised and
    identical everywhere, Windows Terminal included: a 6x6x6 cube from 16 to 231,
    then a 24-step grey ramp.
    """
    if index < 0 or index > 255:
        return None
    if index < 8:
        table = SGR_BG if background else SGR_FG
        return table[(40 if background else 30) + index]
    if index < 16:
        table = SGR_BG if background else SGR_FG
        return table[(100 if background else 90) + index - 8]
    if index < 232:
        offset = index - 16
        levels = (offset // 36, (offset // 6) % 6, offset % 6)
        red, green, blue = (0 if level == 0 else 55 + 40 * level for level in levels)
        return f"#{red:02x}{green:02x}{blue:02x}"
    grey = 8 + 10 * (index - 232)
    return f"#{grey:02x}{grey:02x}{grey:02x}"


def _extended_color(codes: list[int], position: int) -> tuple[str | None, int]:
    """Read one 38/48 extended colour and say where it ends.

    Both forms have to be consumed even when the colour is not used, or their
    arguments are read back as separate codes — 38;2;120;200;80 was landing on
    code 2 and turning the text dim instead of colouring it.
    """
    if position + 1 >= len(codes):
        return None, len(codes)
    background = codes[position] == 48
    mode = codes[position + 1]
    if mode == 5 and position + 2 < len(codes):
        return _xterm_256_color(codes[position + 2], background=background), position + 3
    if mode == 2 and position + 4 < len(codes):
        # 24-bit colour is not reproduced; the nearest cube entry keeps the tone
        # without pretending the terminal has more colours than it shows.
        red, green, blue = codes[position + 2 : position + 5]
        cube = tuple(0 if value < 48 else min(5, (value - 35) // 40) for value in (red, green, blue))
        index = 16 + 36 * cube[0] + 6 * cube[1] + cube[2]
        return _xterm_256_color(index, background=background), position + 5
    return None, position + 2


def _apply_sgr(style: dict[str, Any], payload: str) -> None:
    codes = _sgr_codes(payload)
    if codes is None:
        return

    position = 0
    while position < len(codes):
        code = codes[position]
        step = 1
        if code == 0:
            style.clear()
        elif code == 1:
            style["bold"] = True
            style.pop("dim", None)
        elif code == 2:
            style["dim"] = True
            style.pop("bold", None)
        elif code == 3:
            style["italic"] = True
        elif code == 4:
            style["underline"] = True
        elif code == 7:
            style["reverse"] = True
        elif code == 9:
            style["strike"] = True
        elif code == 22:
            style.pop("bold", None)
            style.pop("dim", None)
        elif code == 23:
            style.pop("italic", None)
        elif code == 24:
            style.pop("underline", None)
        elif code == 27:
            style.pop("reverse", None)
        elif code == 29:
            style.pop("strike", None)
        elif code in (38, 48):
            color, position = _extended_color(codes, position)
            if color:
                style["bg" if code == 48 else "fg"] = color
            elif code == 38:
                style.pop("fg", None)
            else:
                style.pop("bg", None)
            continue
        elif code in SGR_FG:
            style["fg"] = SGR_FG[code]
        elif code == 39:
            style.pop("fg", None)
        elif code in SGR_BG:
            style["bg"] = SGR_BG[code]
        elif code == 49:
            style.pop("bg", None)
        position += step


def _style_attr(style: dict[str, Any]) -> str:
    parts: list[str] = []
    if style.get("bold"):
        parts.append("font-weight:700")
    if style.get("dim"):
        parts.append("opacity:.72")
    if style.get("italic"):
        parts.append("font-style:italic")
    decorations = [
        name
        for flag, name in (("underline", "underline"), ("strike", "line-through"))
        if style.get(flag)
    ]
    if decorations:
        parts.append(f"text-decoration:{' '.join(decorations)}")
    foreground, background = style.get("fg"), style.get("bg")
    if style.get("reverse"):
        # A terminal swaps the pair rather than inventing a colour, and falls back
        # to the panel's own text and background when only one side is set.
        foreground, background = (
            background or "var(--audion-terminal-background, #0b1015)",
            foreground or "var(--audion-terminal-text, #e5e7eb)",
        )
    if foreground:
        parts.append(f"color:{foreground}")
    if background:
        parts.append(f"background-color:{background}")
    return ";".join(parts)


def _emit_html(fragment: str, style: dict[str, Any]) -> str:
    escaped = html.escape(fragment, quote=True)
    attr = _style_attr(style)
    if not attr:
        return escaped
    return f'<span style="{attr}">{escaped}</span>'


def strip_ansi(text: str) -> str:
    """Remove ANSI/OSC/control escapes while keeping printable Unicode text."""
    source = str(text)
    result: list[str] = []
    cursor = 0
    length = len(source)

    while cursor < length:
        char = source[cursor]
        if char == "\x1b":
            cursor, _event = _consume_escape(source, cursor)
            continue
        if _is_control_char(char):
            cursor += 1
            continue
        result.append(char)
        cursor += 1

    return ORPHAN_SGR.sub("", "".join(result))


class AnsiHtmlRenderer:
    """Renders ANSI text to HTML, carrying the style across calls.

    A colour opened on one line and closed on a later one is normal terminal
    output, so the state has to outlive a single line. `ansi_to_html` is the same
    machinery without the memory, for text that stands on its own.

    Every app in the fleet grew its own copy of this class with its own method
    names — `render` and `feed`, `reset` and `finalize`. They all did the same
    work, so all four names are kept and none of the call sites has to change.
    """

    __slots__ = ("style",)

    def __init__(self) -> None:
        self.style: dict[str, Any] = {}

    def reset(self) -> None:
        """Forget the colour in force, as a cleared screen would."""
        self.style = {}

    def finalize(self) -> str:
        """Nothing is left open: each fragment carries its own span."""
        return ""

    def render(self, text: str) -> str:
        source = str(text)
        result: list[str] = []
        plain: list[str] = []
        cursor = 0
        length = len(source)

        def flush() -> None:
            if plain:
                text = ORPHAN_SGR.sub("", "".join(plain))
                plain.clear()
                if text:
                    result.append(_emit_html(text, self.style))

        while cursor < length:
            char = source[cursor]
            if char == "\x1b":
                flush()
                cursor, event = _consume_escape(source, cursor)
                if event and event[0] == "csi" and event[2] == "m":
                    _apply_sgr(self.style, event[1])
                continue
            if _is_control_char(char):
                cursor += 1
                continue
            plain.append(char)
            cursor += 1

        flush()
        return "".join(result)

    feed = render
    render_line = render

    def render_lines(self, lines: Iterable[str]) -> str:
        """The same lines terminal_lines_html would build, without the newlines.

        One app drives its panel through this method rather than through the
        module function, and appends the result to the pre.
        """
        return "".join(
            f'<span class="{TERMINAL_LINE_CLASS}">{self.render(str(line))}</span>' for line in lines
        )


# DocFlow names the same class this way.
StatefulAnsiHtmlRenderer = AnsiHtmlRenderer


def ansi_to_html(text: str) -> str:
    """Render whitelisted SGR ANSI as escaped HTML spans, with no memory."""
    return AnsiHtmlRenderer().render(text)


# Two apps style their terminal under their own prefix; the class is theirs to
# name, the way the sixteen basic colours are.
TERMINAL_LINE_CLASS = "audion-terminal-line"
TERMINAL_PRE_CLASS = "audion-terminal-pre"

BOX_DRAWING = frozenset(chr(code) for code in range(0x2500, 0x2580))
RULE_CHARS = frozenset("-=+_ \t")


def line_holds_a_table(line: str) -> bool:
    """Whether this line is part of a table and must keep its columns.

    Ordinary output wraps, which is right for a long path or a sentence. A table
    row wrapped in the middle of a cell — and then indented by the hanging indent
    the panel gives continuations — arrives as loose bars with nothing lined up.
    Such a line is better left unwrapped, even at the cost of scrolling to read it.

    Three shapes count: box drawing of any kind, a row divided by at least two
    bars, and a horizontal rule of dashes or equals signs.
    """
    stripped = line.strip()
    if not stripped:
        return False
    if any(char in BOX_DRAWING for char in stripped):
        return True
    if stripped.count("|") >= 2:
        return True
    return len(stripped) >= 4 and all(char in RULE_CHARS for char in stripped)


def terminal_lines_html(
    lines: Iterable[str],
    leading_newline: bool = False,
    *,
    renderer: AnsiHtmlRenderer | None = None,
    start_id: int | None = None,
    skip: int = 0,
) -> str:
    # A caller that keeps a renderer between refreshes keeps the colour a tool
    # opened on an earlier line; without one each call starts clean.
    active = renderer or AnsiHtmlRenderer()
    rendered = []
    for offset, line in enumerate(lines):
        # Skipped lines still go through the renderer: the colour they opened has
        # to be in force for the lines that follow.
        line_html = active.render(str(line))
        if offset < skip:
            continue
        if not TERMINAL_LINE_CLASS:
            # One app wraps the lines itself and wants them bare from here.
            rendered.append(line_html)
            continue
        classes = TERMINAL_LINE_CLASS
        if line_holds_a_table(line):
            classes += f" {TERMINAL_LINE_CLASS}-table"
        identity = "" if start_id is None else f' data-terminal-line="{start_id + offset}"'
        rendered.append(f'<span class="{classes}"{identity}>{line_html}</span>')
    if not rendered:
        return ""
    prefix = "\n" if leading_newline else ""
    return prefix + "\n".join(rendered)


def terminal_html(
    lines: Iterable[str],
    *,
    renderer: AnsiHtmlRenderer | None = None,
    history_limit: int | None = None,
    start_id: int | None = None,
    skip: int = 0,
) -> str:
    visible = list(lines)
    if history_limit:
        visible = visible[-history_limit:]
    body = terminal_lines_html(visible, renderer=renderer, start_id=start_id, skip=skip)
    return (
        f'<pre class="{TERMINAL_PRE_CLASS}" spellcheck="false"'
        f' aria-label="Operation terminal">{body}</pre>'
    )


def _windows_oem_encoding() -> str | None:
    if os.name != "nt":
        return None
    try:
        codepage = int(ctypes.windll.kernel32.GetOEMCP())  # type: ignore[attr-defined]
    except Exception:
        return None
    return f"cp{codepage}" if codepage > 0 else None


def _decode_utf16_ish(data: bytes) -> str | None:
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            return None

    sample = data[:200]
    if len(sample) < 4:
        return None
    even_slots = sample[0::2]
    odd_slots = sample[1::2]
    even_nuls = even_slots.count(0)
    odd_nuls = odd_slots.count(0)
    even_total = max(1, len(even_slots))
    odd_total = max(1, len(odd_slots))

    if odd_nuls / odd_total >= 0.35 and even_nuls / even_total <= 0.10:
        try:
            return data.decode("utf-16-le")
        except UnicodeDecodeError:
            return None
    if even_nuls / even_total >= 0.35 and odd_nuls / odd_total <= 0.10:
        try:
            return data.decode("utf-16-be")
        except UnicodeDecodeError:
            return None
    return None


def _unique_encodings(values: Iterable[str | None]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _decoded_score(text: str, priority: int) -> float:
    score = float(priority)
    lower = text.lower()
    score += sum(2.0 for char in text if "а" <= char.lower() <= "я" or char in "ёЁ")
    score += sum(0.2 for char in text if char.isascii() and (char.isalnum() or char.isspace() or char in ":;.,/\\-_[](){}"))
    score -= sum(12.0 for char in text if "\u2500" <= char <= "\u259f")
    score -= sum(8.0 for char in text if char in MOJIBAKE_PENALTY_CHARS)
    score -= text.count("\ufffd") * 20.0
    score -= sum(20.0 for char in text if _is_control_char(char))
    for word in ("ошибка", "файл", "найти", "не ", "уда"):
        if word in lower:
            score += 12.0
    return score


def decode_output_bytes(data: bytes) -> str:
    return decode_process_bytes(data)


SPINNER_FRAME_CHARS = set("-\\|/ \t")


def _is_spinner_only_line(line: str) -> bool:
    """A single spinner frame, left behind after a carriage return became a line.

    A frame is exactly one character being redrawn — `-`, `\\`, `|`, `/` — because
    the carriage return that separates frames has already become a line break by
    the time this runs. Anything longer is content.

    Without that limit this also swallowed the rules of ASCII tables,
    `|-------|-------|`, plain `--------` dividers and the separator row of a
    Markdown table, which is why such tables arrived in the panel as loose bars
    with their frames missing. Dropping a line loses output silently, while
    keeping a stray frame costs one line, so the doubtful cases are kept.
    """
    stripped = line.strip()
    return len(stripped) == 1 and stripped in SPINNER_FRAME_CHARS


def _redrawn_line(part: str) -> str:
    """What a terminal would be showing after the carriage returns in one line.

    A progress bar writes its line again and again separated by `\\r`, never by a
    newline, so a whole tqdm run arrives here as a single part. Turning each `\\r`
    into a line break spilled a hundred redraws into a hundred log lines.

    A carriage return moves the cursor to the start of the line; it does not clear
    it. Each segment is written over what is already there, and whatever the new
    segment does not reach stays visible — which is why a bar that grows leaves
    only its final state, while a short redraw over a long line does not swallow
    the tail.
    """
    if "\r" not in part:
        return part
    rendered = ""
    for segment in part.split("\r"):
        rendered = segment + rendered[len(segment) :]
    return rendered


def _decoded_output_lines(chunk: bytes | str) -> list[str]:
    text = decode_output_bytes(chunk) if isinstance(chunk, bytes) else str(chunk)
    text = text.replace("\r\n", "\n")
    result: list[str] = []
    for part in text.split("\n"):
        line = _redrawn_line(part).rstrip()
        if not line or _is_spinner_only_line(line):
            continue
        result.append(line)
    return result


def iter_process_output_lines(stream: Any) -> Iterator[str]:
    while True:
        chunk = stream.readline()
        if chunk == b"" or chunk == "":
            break
        yield from _decoded_output_lines(chunk)
