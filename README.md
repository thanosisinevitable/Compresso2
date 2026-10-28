# Compresso

A local macOS utility for file compression, image/PDF conversion, duplicate
discovery, version storage and byte-entropy analysis.

- **Compress & Convert:** PNG, JPEG, TIFF, WebP, BMP, PDF and supported ZIP contents.
- **Ghost Hunt:** exact duplicates and visually similar images.
- **Entropy Lab:** Shannon byte entropy, histogram and section heatmap.
- **Version Vault:** shared-chunk archives with verified restoration.
- **Target Lock:** fit images to a size budget.
- **Artifact Lens:** before/after comparison, difference maps and SSIM.

## Run on macOS

Install [Homebrew](https://brew.sh) if needed, then run from this folder:

```bash
brew install node python@3.12 ghostscript
./start
```

Or double-click **Start-Compresso.command**. First launch installs project
dependencies. Keep Terminal open; use **Cmd+Q** to quit.

## Try the samples

The **64 demo files** are included in [samples/](samples/).
Follow the [sample walkthrough](samples/README.md) for every feature, including
conversion examples and suggested settings. Save generated results in `outputs/`.

## Check and build

After setup:

```bash
npm test
npm run lint
npm run build
npm run dist:mac
```

The Mac build goes into `release/`. Native Mac packaging still needs verification.

[Development notes](docs/DEVELOPMENT.md) · [Conversion details](docs/CONVERSION.md) ·
[Test report](docs/TEST_REPORT.md) · [Third-party notices](docs/THIRD_PARTY_NOTICES.md) ·
[Push to GitHub](docs/GITHUB.md)
