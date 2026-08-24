# FFmpeg Build Review

FFmpeg licensing depends on the exact build configuration and bundled libraries. Some builds are LGPL, some are GPL, and builds using nonfree options are not redistributable as normal FOSS release assets.

Before publishing an archive that bundles FFmpeg binaries:

- record `ffmpeg -hide_banner -version`;
- record `ffmpeg -hide_banner -buildconf`;
- identify the exact package source and commit/build page;
- include or link the matching FFmpeg source offer/build information;
- do not redistribute builds marked nonfree or built with `--enable-nonfree`.

References:

- https://www.ffmpeg.org/legal.html
- https://www.gyan.dev/ffmpeg/builds/
