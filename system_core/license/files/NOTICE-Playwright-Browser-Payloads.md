# Playwright Browser Payload Review

The Python `playwright` package is collected as a normal Python dependency, but downloaded browser payloads such as Chromium, Firefox, or WebKit are separate redistributed binaries.

Before publishing a release archive that bundles Playwright browser folders, include the exact browser payload notices and license texts from the downloaded browser package.

References:

- https://playwright.dev/python/
- https://github.com/microsoft/playwright
