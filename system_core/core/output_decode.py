from __future__ import annotations

from dataclasses import dataclass
import locale


MOJIBAKE_MARKERS = {
    "\ufffd",
    "Ð",
    "Ñ",
    "Ћ",
    "Ў",
    "Є",
    "Ґ",
    "¤",
    "©",
    "«",
    "»",
    "╨",
    "╤",
    "╬",
    "├",
    "┬",
}
UTF8_CYRILLIC_AS_CP866_MARKERS = {"╨", "╤"}

MOJIBAKE_SEQUENCES = (
    "Р°",
    "Р±",
    "РІ",
    "Рі",
    "Рґ",
    "Рµ",
    "Рё",
    "Р№",
    "Рє",
    "Р»",
    "Рј",
    "РЅ",
    "Рѕ",
    "Рї",
    "СЂ",
    "СЃ",
    "С‚",
    "Сѓ",
    "С„",
    "С…",
    "С†",
    "С‡",
    "С€",
    "С‰",
    "С‹",
    "СЊ",
    "СЌ",
    "СЋ",
    "СЏ",
    "С‘",
    "Р”",
    "Рџ",
    "РЎ",
    "Рњ",
    "Рќ",
    "Рћ",
    "Р­",
    "â€¦",
    "â€",
    "â„",
    "â€“",
    "â€”",
    "тА",
    "тВ",
    "тГ",
    "тД",
    "тЕ",
    "тЖ",
    "тЗ",
    "тИ",
    "тК",
    "тЛ",
    "тМ",
    "тН",
    "тО",
    "тП",
    "тР",
    "тС",
    "тТ",
    "тУ",
    "тФ",
    "тХ",
    "тЦ",
    "тЧ",
    "тШ",
    "тЩ",
    "тЪ",
    "тЫ",
    "тЬ",
    "тЭ",
    "тЮ",
    "тЯ",
)

COMMON_RUSSIAN = set("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯабвгдеёжзийклмнопрстуфхцчшщъыьэюя")


@dataclass(frozen=True)
class DecodeCandidate:
    text: str
    encoding: str
    score: int


def _candidate_encodings(data: bytes) -> list[str]:
    encodings: list[str] = []

    def add(encoding: str | None) -> None:
        if not encoding:
            return
        normalized = encoding.lower().replace("_", "-")
        if normalized not in encodings:
            encodings.append(normalized)

    add("utf-8")
    if _looks_utf16(data):
        add("utf-16")
        add("utf-16-le")
        add("utf-16-be")
    add("cp866")
    add(locale.getpreferredencoding(False))
    add(locale.getencoding() if hasattr(locale, "getencoding") else None)
    add("mbcs")
    add("cp1251")
    return encodings


def _looks_utf16(data: bytes) -> bool:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return True
    if len(data) < 4:
        return False
    sample = data[: min(len(data), 200)]
    even_nuls = sample[0::2].count(0)
    odd_nuls = sample[1::2].count(0)
    return max(even_nuls, odd_nuls) >= max(2, len(sample) // 5)


def _score_text(text: str, encoding: str) -> int:
    score = 0
    if encoding == "utf-8":
        score += 20
    for char in text:
        code = ord(char)
        if char in COMMON_RUSSIAN:
            score += 8
        elif char.isascii() and (char.isprintable() or char in "\r\n\t"):
            score += 2
        elif _is_terminal_graphic(char):
            score += 30 if char not in MOJIBAKE_MARKERS else 0
        elif char.isprintable():
            score += 1
        if char in MOJIBAKE_MARKERS:
            score -= 60 if char in UTF8_CYRILLIC_AS_CP866_MARKERS else 20
        if code < 32 and char not in "\r\n\t":
            score -= 30
    score -= text.count("\x00") * 40
    score -= text.count("����") * 80
    for sequence in MOJIBAKE_SEQUENCES:
        score -= text.count(sequence) * 120
    return score


def _is_terminal_graphic(char: str) -> bool:
    code = ord(char)
    return (
        0x2500 <= code <= 0x257F
        or 0x2580 <= code <= 0x259F
        or 0x2800 <= code <= 0x28FF
    )


def decode_process_bytes(data: bytes) -> str:
    if not data:
        return ""

    candidates: list[DecodeCandidate] = []
    for encoding in _candidate_encodings(data):
        try:
            text = data.decode(encoding, errors="strict")
        except (LookupError, UnicodeDecodeError):
            continue
        candidates.append(DecodeCandidate(text, encoding, _score_text(text, encoding)))

    if candidates:
        return max(candidates, key=lambda candidate: candidate.score).text
    return data.decode("utf-8", errors="replace")


def decode_process_output(data: bytes) -> str:
    return decode_process_bytes(data)
