# Compresso 2.2

An Electron + React + Python desktop utility for **compression, version storage, duplicate discovery and byte-entropy analysis**. Everything runs locally. The original dark visual identity, concentric rings, TIFF choices and four PDF presets are retained.

**Delivery status:** implementation and automated checks are included. This archive is source code, not a prebuilt macOS application. See `TEST_REPORT.md` for verified results and the native macOS checks still required.

## New in 2.2

- Fixed Artifact Lens rejecting internally created images under macOS temporary-folder aliases.
- Replaced the TIFF-only output control with **Convert to**: PNG, JPG, TIFF,
  WebP, BMP and PDF. The selected format applies to every supported input.
- PDF-to-image export includes every page, with 72/150/300 dpi selection.
- Multipage TIFF/PDF destinations retain pages in one file per document;
  PNG/JPG/WebP/BMP export one image per page, packaged in ZIP when needed.
- Conversion options reset stale results so the next action uses the displayed
  format/resolution/preset. Actual symlink and archive safeguards remain active.

Choose **Keep original** for the existing compression behavior.
See **CONVERSION.md** for the exact conversion matrix and limitations. Supported
inputs are PNG/JPEG/TIFF/WebP/BMP/PDF and ZIP; Word DOC/DOCX is not supported.

## New in 2.1

The three main sections stay **Compress**, **Ghost Hunt** and **Entropy Lab**. Compress now contains three focused tools: **Standard**, **Target Lock** and **Version Vault**. Artifact Lens opens from an image result instead of adding another main screen.

| Feature | How to use it | What it demonstrates |
| --- | --- | --- |
| Target Lock | Choose 1–100 single-frame images, enter a maximum per-image size in KiB and click **Lock target**. Enable resizing only if you want it. Inspect or save successful results. | Measured rate/quality trade-offs and bounded search. |
| Artifact Lens | Select **Inspect image** after Standard compression, or **Inspect** on a Target Lock result. Move the before/after slider, zoom, or view amplified differences/heatmaps. | Structural similarity (SSIM) and pixel-error visualization. |
| Version Vault | Choose 2–200 related files, arrange the timeline, build and save a `.cvault`. Use **Open & restore** to recover one version or all versions. | Content-defined chunk deltas, shared storage, lossless reconstruction and SHA-256 integrity. |

**Updating from 2.0, 2.1 or an earlier copy:** extract this updated source into a fresh folder and open `Start-Compresso.command` (or run `./start`). The launcher installs the matching project dependencies automatically. Keep your own saved outputs outside the old source folder. The added Python dependency is scikit-image; no new native command-line tool or background service is needed.

### Target Lock details

Each target is measured in **KiB (1,024 bytes)**, not decimal KB. The allowed range is 1 KiB–100 MiB. New outputs are JPEG with quality searched from 1–95, progressive encoding and an sRGB profile. Transparency is explicitly flattened onto white. PNG/TIFF/WebP/BMP inputs are conversions to JPEG in this tool; Standard compression keeps its previous format behavior. Animated and multipage inputs are rejected rather than silently dropping pages.

The search records every attempted quality, dimension and byte size. Selected outputs are checked against the requested byte limit. The highest quality found is used; the bounded search is not a proof of a global quality optimum. An existing JPEG already under the limit is copied unchanged. Dimensions remain unchanged unless **Allow resizing** is enabled, and any resulting resize is shown explicitly. Infeasible inputs have no saved output; a mixed batch saves only successful images. The enclosing ZIP has its own overhead, so its size is not the sum of the per-image budgets alone.

### Artifact Lens details

Both images are orientation-corrected and converted to sRGB for comparison. Previews and SSIM measurement are bounded to a 1,600 px edge. The viewer offers 1×/2×/4× preview zoom, before/after clipping, amplified absolute RGB differences and a color-coded mean-error map. Amplification can be changed from 1× to 32×. A brighter difference is not a prediction of perceptual importance.

SSIM is computed by scikit-image on the comparable preview; it is a structural metric, **not a percentage of quality preserved**. If output dimensions changed, the reference is resized to match and the UI warns that the score does not capture the lost original resolution. Very small images can have an unavailable SSIM score. Standard output comparisons are available for single-frame PNG/JPEG/TIFF images (up to the first 50 image outputs of a batch), including TIFF→JPG; single-frame WebP/BMP can be inspected through Target Lock. Comparisons recheck source identity and fail if the original has changed.

### Version Vault details

The first file starts the ordered timeline. Shared content chunks are stored once; later versions store references plus new compressed chunks. Whole-file fallback is used when chunk storage is less efficient. Each version restores independently without walking a long patch chain. Every created archive is reconstructed and SHA-256 verified before saving; opening reads the index, while restoration fully verifies the selected payloads. All operations preserve source files.

Version Vault works on arbitrary file bytes and uses a documented Python content-defined chunk delta format, **not xdelta/VCDIFF**. This avoids adding another native executable to Mac packaging. See `VAULT_FORMAT.md` for the container and restore rules. Similar-looking, re-encoded images may share few bytes; savings are not guaranteed, and the UI reports archive overhead when a vault grows. Only basenames and file contents are restored, not Finder tags, permissions or folders. The complete `.cvault` is required; save it before quitting.

## Start on your Mac

**Double-click `Start-Compresso.command`.** It prepares the project's Python
and npm dependencies on first launch, then opens the app. Later launches reuse
them. No virtual-environment activation or separate backend command is needed.

If you prefer Terminal, open it in this folder and run:

```bash
./start
```

Install the prerequisites once if needed (with [Homebrew](https://brew.sh)):

```bash
brew install node python@3.12 ghostscript
```

Use a native terminal on Apple Silicon, not a Rosetta terminal. The launcher
requires Node 22+ and Python 3.11-3.13 (3.12 recommended). It checks for missing
prerequisites and explains what to install. Python/npm installation needs
internet on the first launch and after dependency updates. Processing runs
locally. It does not install Homebrew or change system packages automatically.

Keep the Terminal window open while the app is running. **Cmd+Q** quits and stops
its backend. Closing the last window keeps the app in the Dock, as on macOS.

If executable permissions were removed while extracting, run this once:

```bash
chmod +x start Start-Compresso.command
./start
```

The existing `npm run dev` command still works after setup. For a production
frontend without a live development server, use `npm start` after setup.
To build on a Mac, install Apple's command-line tools with
`xcode-select --install` if they are not installed already.

## Build the macOS app and DMG

On the same Mac, with the dependencies above installed:

```bash
npm run dist:mac
```

The command builds the current native architecture. On an Apple Silicon Mac it builds **arm64**. Intel builds should be made on an Intel Mac using x64 Node and Python; this project does not attempt a universal Python bundle or cross-compilation.

The build performs these steps:

1. Freeze Python, Pillow, ImageHash, SciPy, scikit-image, FastAPI and the application modules using PyInstaller.
2. Copy Ghostscript, its non-system dynamic libraries, fonts and resource files; rewrite dynamic-library references relative to the bundle and apply ad-hoc signatures.
3. Run a smoke test against the frozen backend, including entropy, pHash, SHA-256, PDF compression, Target Lock, comparison assets, vault restoration and shutdown.
4. Build React with Vite and create the `.app`, `.dmg` and ZIP with Electron Builder.

Outputs are in `release/`. Typical Apple Silicon outputs:

- `release/mac-arm64/Compresso.app`
- `release/Compresso-2.2.0-arm64.dmg`
- `release/Compresso-2.2.0-arm64.zip`

The configuration is for a **local, unsigned/ad-hoc university build**, not a notarized public release. Developer ID signing and notarization need your own Apple credentials and testing. No credentials are included or needed for local development. The packaging command intentionally refuses to run on Linux or Windows; a successful frontend build is not evidence that a Mac installer works.

Before sharing the packaged app, complete the native checklist in `TEST_REPORT.md`, including launching a relocated copy without Homebrew available. Third-party licensing notes are in `THIRD_PARTY_NOTICES.md`.

## Using Compresso

### Compress

The following table describes **Keep original**. Choose a specific
format in **Convert to** for the conversions described in CONVERSION.md.
The old `tiffMode` API remains supported for compatibility.

Choose or drop files, set the existing PDF/TIFF options, and select **Compress files**. Save the result with a native **Save as…** dialog. Your source files are never overwritten. The save action rejects the source path and hard links to a source.

| Input | Output and behavior |
| --- | --- |
| PNG | Lossless optimized PNG; transparency retained. Animated PNG frames are retained by Pillow. |
| JPG/JPEG | JPEG quality 75, progressive, maximum 1920 px edge, with orientation applied. This is lossy. |
| TIF/TIFF → Keep TIFF | Lossless Deflate TIFF; multipage files retain every page. |
| TIF/TIFF → JPG | Full-resolution JPEG quality 85; one file per page. Transparent pixels are composited onto white. |
| TIF/TIFF → PDF | All TIFF pages merged into one PDF, in input order. ZIP entries use archive order. Individual page images are processed sequentially, using temporary page PDFs. |
| WebP/BMP | Retain the format. WebP attempts lossless optimization; BMP remains a bitmap. |
| PDF | Ghostscript presets: Extreme `/screen`, High `/ebook`, Medium `/printer`, Low `/prepress`. Presets can change image quality. |
| ZIP | Supported images/PDFs are extracted and processed. Nested paths are preserved; unsupported/hidden entries are reported and skipped. Output is a ZIP. |
| Multiple files | A ZIP of outputs. Mixed supported types are accepted. Duplicate output names receive deterministic numbered suffixes. |

Same-format compression retains the original bytes if the attempted output is larger or equal. Explicit conversion can produce a larger file. ZIP safety limits are 20,000 entries and 10 GiB of expanded data. Password-protected, corrupt or unsafe archives fail with a clear error. The input-size statistic for a ZIP refers to supported extracted content, not the compressed archive's original size.

### Ghost Hunt

Select or drop **one folder**. Exact matches use file size first, then streaming SHA-256. Optional visual matching uses Pillow + ImageHash's 64-bit pHash. The slider selects a maximum Hamming distance from 0 to 16; a higher value admits more candidates. A displayed percentage is `100 × (1 − distance / 64)`, **not a confidence probability**.

Each visual candidate is compared with its group's reference. The grouping uses a BK-tree of anchors, avoids misleading transitive similarity chains and is deliberately not an exhaustive all-pairs image search. One representative of each exact-duplicate set is included in visual matching. This keeps exact-copy savings separate. PNG, JPEG, TIFF, WebP, BMP and GIF images can be compared; TIFF/GIF use the first frame. Cropped/rotated images or visually simple images may be missed or produce false matches. Always preview visual candidates.

No files are selected automatically. **Select extra exact copies** is an explicit user action and never adds visual-only candidates. Preview uses macOS Quick Look; reveal uses Finder. **Move to Trash…** requires a native confirmation. The backend checks group membership, retained copies and file identities, re-hashes affected exact groups, and rechecks after confirmation. Electron checks identities once more immediately before each Trash operation. Partial failures are reported and stop further moves; rescan after any successful cleanup.

Directory symlinks, file symlinks, special files and hard-linked files are excluded. Unreadable/changed files are reported without aborting the entire scan. A 200,000-file cap keeps the in-memory index and results manageable. Savings are logical byte estimates: APFS clones, filesystem allocation and Trash mean actual immediately freed disk space may differ. Do not move/edit the scanned folder while performing cleanup.

### Entropy Lab

Any regular local file can be analyzed, including formats not accepted by Compress. Every byte is counted using bounded 1 MiB read buffers. No file is uploaded or modified.

- **Shannon entropy:** `H = −Σ p(x) log₂ p(x)`, over byte values 0–255.
- **Byte distribution:** all 256 counts; hover the chart for counts and percentages.
- **Redundancy:** `100 × (1 − H / 8)`, an empirical zero-order statistic.
- **Heatmap:** at most 256 consecutive sections; hover, click or keyboard-focus a cell for its byte offset, length and entropy.

An empty file has no empirical distribution: entropy and redundancy are shown as undefined. Small samples can bias entropy downward. High byte entropy neither proves encryption nor guarantees that further compression is impossible: byte order and repeated sequences are not captured by a zero-order histogram. Explanations are deterministic rules, not AI.

## Tests

```bash
npm test
npm run lint
npm run build
npm run test:package
npm run test:ui:dom
python scripts/smoke_backend.py
```

For the real-backend browser integration suite, install its test browser once:

```bash
npx playwright install chromium
npm run test:ui
```

Both UI suites use the real Python algorithms while replacing native dialogs and shell actions with deterministic test fixtures. The DOM suite checks React behavior without a graphical browser; the Playwright suite adds actual rendering and screenshots. It never trashes real user files. Screenshots and test outputs go into ignored `.qa/`. It does not replace testing Finder, Quick Look, native drag/drop and Trash on a Mac.

## How the pieces fit

- `main.js`: native window, file dialogs, vetted IPC, saving, previews and confirmed Trash.
- `preload.cjs`: narrow context-isolated bridge; `webUtils.getPathForFile` handles dropped files.
- `electron/backend.mjs`: backend startup, readiness handshake, private token and teardown.
- `backend/main.py`: authenticated loopback API and two-worker background job queue.
- `backend/compressor.py`, `converter.py`, `duplicates.py`, `entropy.py`: compression/conversion, duplicate discovery and analysis.
- `backend/imaging.py`, `vault.py`: Target Lock, Artifact Lens and streaming version archives.
- `src/CompressHub.jsx`, `GhostHunt.jsx`, `EntropyLab.jsx`: the three persistent sections; the Compress hub includes Standard, Target Lock and Version Vault.
- `scripts/build_backend.py`, `package.mjs`: native Mac packaging.

The OS assigns a free backend port. Only Electron's main process has the random authentication token; the renderer never connects to the backend directly. The packaged renderer has a Content Security Policy, no Node integration and a sandboxed preload. No public server, database, telemetry, accounts, model or background daemon is installed.

Results live in memory and temporary directories, with a bounded history of up to 12 operations. The backend cleans these on normal shutdown. It watches Electron's stdin pipe so a parent crash also triggers shutdown. A forced operating-system kill may leave temporary files for the OS to reclaim. Large image decoding still needs memory proportional to an image/frame; streaming avoids loading entire arbitrary files or entire archives in memory.

## Troubleshooting

- **Engine missing:** create `.venv` and install the Python requirements from the project root. A custom Python executable can be supplied through `COMPRESSO_PYTHON`.
- **Ghostscript missing:** run `brew install ghostscript`, then restart the engine. PDF compression and multipage TIFF-to-PDF merging require it. Standard Apple Silicon and Intel Homebrew executable paths are included during development.
- **Permissions:** choose a folder you can access. macOS may ask permission for Documents, Desktop or external drives; unreadable entries are reported.
- **Port 5173 busy:** stop the other Vite server and retry `npm run dev`. The Python port is always automatic.
- **Backend stops:** use **Restart engine**. Existing result IDs expire after a restart, so repeat the operation.
- **Packaging architecture error:** confirm `node -p process.arch` and `python -c "import platform; print(platform.machine())"` agree. Recreate `.venv` using the correct native Python if necessary.
- **Unsupported Ghostscript installation layout:** use the Homebrew installation. The packager fails explicitly if it cannot resolve native dependencies rather than shipping a broken runtime.
