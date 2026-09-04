# Audion Yandex Portable - user guide

**Contents**

- [How the window works](#how-the-window-works)
- [First run](#first-run)
- [What is inside the build](#what-is-inside-the-build)
- [Updating](#updating)
- [Build settings](#build-settings)
- [Worth knowing](#worth-knowing)

This program makes a portable Yandex Browser: one that lives in a folder, starts
from anywhere, and is never installed into Windows. Everything the browser
remembers about you — bookmarks, tabs, passwords — stays inside that same folder.

## How the window works

Three tabs across the top: `INSTALL`, `UPDATE`, `SERVICE`. That is the whole
menu: press a tab and its commands, with their settings, are right underneath.
Above the tabs sits a service strip with the folder cleanups, which belong to the
program as a whole.

Choices are made with buttons — the chosen one washed with blue, the rest
outlined. Captions are short; the explanation appears in the tooltip when the
pointer rests on a button or a checkbox.

## First run

1. Tab `SERVICE` → `7-ZIP`. Without it the installer cannot be unpacked.
2. Tab `INSTALL` → `BUILD`.

About 200 MB is downloaded and roughly 500 MB unpacked. The finished build
appears in the Target folder (`output\Portable\Yandex Browser Portable`). Start
it with `Yandex Browser Portable.cmd` in its root.

The folder can go anywhere: another drive, a flash drive, a colleague. The
profile travels with it.

## What is inside the build

| Folder or file | What it is |
| --- | --- |
| `App` | The browser itself. Replaced wholesale on update. |
| `Data` | Your profile: bookmarks, passwords, tabs, extensions. |
| `Cache` | Cache. Safe to delete, nothing is lost. |
| `Yandex Browser Portable.cmd` | Starts the browser. |
| `Portable-Build.json` | Which versions are inside — browser and Chrome++. |

## Updating

The `UPDATE` tab.

`CHECK` shows what is published next to the version of your build. Nothing is
downloaded: the version is read out of the download link. Worth running first —
the installer itself is 200 MB.

`UPDATE` replaces only the browser inside the build: `Data` and `Cache` are left
alone, so the profile stays. If the browser is already current, nothing is
downloaded at all.

**The update happens where the build lies.** Point Source at its folder — a flash
drive, a network share, wherever it lives — and it is updated in place. Nothing
has to be copied, and the Target folder is not used here: that one is for new
builds. With nothing in Source, the program looks in `output\Portable`.

`CHROME++` is for when the browser should not be touched: `version.dll` and
`chrome++.ini` are replaced directly in the build — 180 KB. The wrapper is
released more often than the browser.

## Build settings

**Leave no traces in Windows.** The browser keeps service counters in the Windows
registry rather than in the profile. This tells the build to erase that branch
when the browser closes, so nothing of it is left behind.

Clear it when a normally installed Yandex Browser is present on the machine: the
branch is shared, and the portable build would erase the installed one's counters.

**Remove the built-in updater.** Leave it on. Otherwise Yandex's own updater will
one day install the browser into the system past the portable folder, and the
point of the build is gone. Updating the build is this program's job.

**Pack into an archive.** Turn it on when the build is to be handed over: one
file instead of a folder. The format sits next to it — `ZIP` opens anywhere, `7Z`
is smaller but needs 7-Zip on the other side. For your own use a folder is
handier — it runs straight away.

**Portability.** What keeps the profile inside the build folder. `CHROME++` is
the wrapper this program started with: its `version.dll` goes next to the
browser. `PROXY LIBRARY` is another wrapper of the same kind, by neyrostalker: it does
the same job, additionally blocks writes to the registry, and Microsoft's
antivirus does not treat it as a threat. The differences and the check results are in
`docs/CHROME_PLUS_AND_DEFENDER.md`.

**Wrapper architecture.** Leave it at `X64`. That is what Yandex ships for
Windows, and the architecture has to match.

**Keep working files** (under `Advanced`). The download and the unpacked
installer stay in `workspace` — useful when a build failed and the reason has to
be found.

## Worth knowing

Yandex Browser already trusts the Russian Ministry of Digital Development
certificates, so there is nothing to install for them, and the browser does not
change the system store. That is usually the point of a portable build: sites
issued against those certificates open, and the system stays clean.

The first start takes longer than usual — the browser is laying out the profile.
After that it starts as always.
