# Audion Yandex Portable

<!-- audion:release -->
<p align="center">
  <a href="https://audion.dev/downloads/yandex-portable"><img alt="Windows" src="https://img.shields.io/badge/Windows-10%20%7C%2011-0b6db8?style=flat-square&logo=windows&logoColor=white"></a>
  <a href="https://github.com/Tensionix/yandex-portable/releases/latest"><img alt="Release" src="https://img.shields.io/github/v/release/Tensionix/yandex-portable?style=flat-square&label=release&color=e08a63"></a>
  <a href="https://github.com/Tensionix/yandex-portable/releases"><img alt="Downloads" src="https://img.shields.io/github/downloads/Tensionix/yandex-portable/total?style=flat-square&label=downloads&color=5fd08a"></a>
  <a href="https://github.com/Tensionix/yandex-portable/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/Tensionix/yandex-portable?style=flat-square&color=5fd08a&logo=apache&logoColor=white&cacheSeconds=3600"></a>
</p>

**Версия 1.0.2** · 2026-09-02 · 82.2 MB

- [Скачать напрямую](https://dl.audion.dev/yandex-portable/1.0.2/Audion_Yandex_Portable_v1.0.2_Full.zip) — быстрая раздача, без ограничений
- [Страница проекта](https://audion.dev/downloads/yandex-portable) — все версии и установка

<p align="center"><img src="docs/screenshot.png" alt="Окно программы" width="560"></p>

`SHA-256: c98a2d9c8e19b175eac9ecae8dfc4ce0304b4237c805ace46bfd863994222284`

---

Проект набора **Audion** — издаёт [Tensionix](https://github.com/Tensionix).
<!-- /audion:release -->


[Русский](README_RU.md) · [User Guide](USER_GUIDE_EN.md)

Builds a portable Yandex Browser, keeps it updated, and keeps Chrome++ current —
the add-on the portability itself rests on.

## Why It Exists

Yandex Browser has no portable build, and there are two reasons to want one — the
second not obvious.

**First: the browser is separated from the system and travels as a folder.** The
ordinary benefit of portability.

**Second: the Russian state root certificates are already embedded in it.**
Russian state portals issue certificates absent from the Windows store; other
browsers will not open those sites without them, so the roots have to be
installed into the system. Yandex Browser carries them itself — which means a
portable build opens such sites **without touching the system certificate store
at all**.

Nothing is installed into Windows: the distribution is unpacked, not run.

## How It Works

The full distribution is an executable with exactly one archive of the browser in
its resources. The program extracts it and lays it out into a build folder: the
browser, the profile, a launcher.

## Chrome++

The build's portability rests on it, so it is updated alongside the browser
itself.

One thing is worth knowing: **a build can fail during packing with a file access
error** — and that is neither the disk nor a corrupt archive, but the antivirus
inspecting a freshly written executable. Covered in
`tools\CHROME_PLUS_AND_DEFENDER.md` (Russian).

## Next

* [User Guide](USER_GUIDE_EN.md) — step by step.
* [Checklist](SMOKE_TEST_RU.md) — what is run before a release (Russian).
* `tools\CHROME_PLUS_AND_DEFENDER.md` — Chrome++ and the antivirus.
* `tools\DECISIONS_EN.md` — decisions taken.

---

## Technical Reference

### What Is in the Build

The browser, a profile with bookmarks and extensions, a launcher, and a record of
which versions are inside. It travels whole and leaves no trace in the system.

### Updating

What the vendor released is compared against what is in the build. Only what
changed is updated; the profile is left alone.
