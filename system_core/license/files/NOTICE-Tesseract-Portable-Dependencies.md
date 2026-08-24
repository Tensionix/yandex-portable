# Tesseract Portable Dependency Review

Tesseract OCR and official `tessdata` repositories are Apache-2.0, but common Windows "portable" payloads are usually staged from a third-party installer or an existing Windows installation.

Such payloads normally include native dependency DLLs such as Leptonica, Cairo, FreeType, HarfBuzz, ICU, OpenSSL, libpng, libtiff, zlib, zstd, and other libraries. These files are not covered by a single Tesseract license.

Before publishing a binary release that includes a staged Tesseract runtime, collect and verify notices for every redistributed native DLL in that folder. Treat the native DLL bundle as a release blocker until provenance and license texts are recorded.

References:

- https://tesseract-ocr.github.io/tessdoc/
- https://github.com/tesseract-ocr/tesseract
- https://github.com/tesseract-ocr/tessdata_fast
- https://ub-mannheim.github.io/Tesseract_Dokumentation/Tesseract_Doku_Windows.html
