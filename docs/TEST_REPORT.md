# Verification report — Compresso 2.2

This source update fixes the Artifact Lens macOS-style temporary-path alias
failure and expands Standard to general image/PDF conversion. It contains
source code, not a prebuilt Mac installer.

## Current checks

- Backend/API suite: **126 tests passed**, including 36 image/PDF format pairs,
  transparency, alpha flattening, EXIF rotation, high-depth grayscale, no silent
  clipping, animated frames, multipage outputs, resolution settings, ZIP naming,
  source preservation and the Mac-style temp-alias regression for both direct
  image and extracted-ZIP comparisons.
- Real-backend React DOM workflows passed, including selecting output format,
  actual PNG-to-JPEG saving, PDF page export and changing rendering resolution.
  These ran with an aliased temporary root to exercise the path fix end to end.
- ESLint, production Vite build and Electron Builder configuration checks passed.
- Source-backend smoke passed authenticated startup, existing tools, image
  conversion, PDF raster export and shutdown on parent disconnect.
- PyInstaller produced a frozen Linux backend. Its smoke suite passed image
  conversion and PDF rendering as well as the existing tools and shutdown.
- ZIP CRCs, safe member paths and launcher executable modes are checked in the
  final source archive.

The backend suite reports one existing Starlette/httpx deprecation warning.
React's DOM harness can report a thumbnail act() warning and reduced-motion
notice. The suites still pass. No new runtime dependency is required by the
converter; it reuses Pillow, ReportLab and Ghostscript.

## Native verification still required

Actual Mac Electron rendering, Finder dialogs, Quick Look/Trash, direct Finder
launcher execution, Apple Silicon/Intel frozen builds and .app/.dmg creation
remain unverified here. Linux freezing and DOM tests do not establish those
native behaviors. PDF-to-image exports are raster images, not editable Word
conversions. Supported document input is PDF; DOC/DOCX is not supported.

## Historical validation

The following notes retain previous-version results and limitations.

## Previous 2.1 verification

Verified on 28 October 2026 in Linux x86_64 using Python 3.12.14 and Node 24.22.1. This is an updated source project. No macOS installer binary is included.

## Passed

| Check | Result |
| --- | --- |
| `npm test` | **71 Python/backend/API tests passed.** One Starlette dependency deprecation warning from its httpx test adapter. |
| `npm run lint` | Passed. |
| `npm run build` | Passed; production renderer bundles generated. |
| `npm run test:package` | Passed against Electron Builder's schema, Mac target/resource declarations and strict production CSP. This validates configuration, not a Mac installer. |
| Source-backend smoke test | Passed authenticated startup, unauthorized-request rejection, entropy, exact and visual scan, PDF, Target Lock, Artifact Lens image assets, vault create/open/verified restore and shutdown on parent disconnect. |
| Frozen Linux backend | PyInstaller build passed. The same smoke suite passed against the frozen executable, including scikit-image SSIM and preview assets. This resolves the new Python-module inclusion check on Linux, not the macOS architecture/signing checks. |
| `npm run test:ui:dom` | Passed the real-backend React workflows below, with native dialogs and shell actions represented by deterministic substitutes. |

The existing compression, duplicate and entropy test cases remain present. New coverage includes:

- A target result is actually within its byte budget and keeps its dimensions by default.
- Infeasible constraints expose no saveable output; explicitly allowed resizing can make a small target feasible.
- Existing JPEGs already under budget retain their bytes. Batch filename collisions do not overwrite outputs, and each JPEG in the ZIP meets its individual budget.
- Multipage inputs are refused by Target Lock rather than silently losing pages; transparency is flattened onto white; EXIF orientation is applied.
- Identical image previews produce SSIM 1.0 and a black difference heatmap; lossy outputs show measured differences. Resized references and tiny images are handled explicitly.
- Changed-source/archive refusal and string-encoded file identities preserve timestamp precision through JSON/JavaScript.
- Version Vault shares regions after inserted/edited bytes, chooses a full-file fallback for unrelated data, and restores exact bytes for single versions and all-version ZIP exports.
- Identical files, empty files, cancellation, invalid version IDs, corrupt chunk hashes, unsafe filenames and decompression overflow are checked.
- Chunk boundaries are independent of I/O read-block sizes.

## React interaction checks

The DOM suite passed:

1. Existing choose → Python compression → save/reveal workflow.
2. Existing exact/perceptual results, manual selections, cancelled cleanup, preview and retained-copy guard.
3. Existing entropy results, 256 histogram bars, heatmap keyboard selection, empty files and preserved navigation state.
4. Opening Artifact Lens from an actual compression output, receiving real SSIM and image assets, moving the split, switching to the heatmap, changing preview zoom and closing the dialog.
5. Setting a Target Lock budget, encoding through Python and saving its result.
6. Creating and saving a vault, opening the saved `.cvault`, restoring a selected version and comparing the restored bytes with the original fixture.

Native file dialogs, real Finder/Trash and the Electron preload are not replaced by this test evidence. The DOM suite checks React behavior and does not perform pixel-level layout inspection.

## Unverified here

- Graphical browser rendering, Retina layout, visual animation quality and image comparison color appearance on a real display. The graphical Playwright suite remains included; it was not run for this update.
- Native Electron runtime, Finder dialogs and drops, Quick Look and actual Trash operations on macOS.
- Native macOS PyInstaller output, relocated Ghostscript, Apple Silicon/Intel `.app` and `.dmg` creation/launch. These require a Mac; the native build command retains its platform guard.
- Developer ID signing, notarization and public Gatekeeper distribution. The default remains an unsigned/ad-hoc local build.
- Large production-scale imaging collections or fidelity certification. Memory is bounded for byte I/O and previews, while image decoding still requires frame-sized buffers and vault indexes grow with chunk references.

## Mac verification checklist

Use disposable copies for cleanup checks.

1. Follow README setup and launch on Apple Silicon. Check all three main sections and the Standard/Target Lock/Version Vault tool navigation.
2. Exercise compression presets and conversions, including transparent PNG and single/multipage TIFF. Verify original files remain unchanged.
3. Target a batch at a strict size limit. Confirm saved JPEG byte sizes, no-resize behavior, infeasible results, explicit resize behavior and collision-safe output names.
4. Inspect both Standard and Target Lock outputs. Check split/zoom/scroll, difference/heatmap amplification, keyboard focus and Escape. Validate the resize caveat, preview-resolution label and color appearance.
5. Build a vault from real related versions, including a Unicode filename. Save, quit, reopen it and restore individual and all versions. Compare restored hashes. Confirm opening a corrupt vault fails safely.
6. Check native folder drops, Quick Look, Finder reveal, cancelled Trash, confirmed Trash and restore from Trash. Confirm a retained copy remains.
7. Check Cmd+W, Dock reopening, Cmd+Q, engine restart and absence of owned Python/Ghostscript processes after quitting.
8. Run all README checks and `npm run dist:mac`. Its frozen-backend smoke test now includes all new features before packaging.
9. Launch the `.app` after relocating it to a folder containing spaces, without relying on an installed Python or Homebrew paths. Repeat from the mounted DMG and installed copy. Test Intel separately if distributing x64.

The manual macOS CI workflow is included but was not dispatched during this work.


## UI and simplified-launch update

Verified with this source update:

- ESLint and production Vite build pass.
- All 71 existing backend/API tests pass.
- The React DOM suite passes against the live Python backend, including
  compression, duplicate scanning, entropy, comparisons, targets and vaults.
- Launcher shell syntax and simulated first setup, repeat launch, dependency
  refresh, paths containing spaces, unsupported Node, missing Python and failed
  installation checks pass. Installations were stubbed; no Mac setup was run.
- Rings and orb now share the same DOM layout anchor and their animation only
  scales about the common center. CSS provides themed scrollbars on all scroll
  surfaces, with a forced-colors fallback.
- The separate 64-file sample pack passed real backend checks: all PDF presets,
  PNG pixel/alpha preservation, TIFF page preservation and conversions, safe
  mixed ZIP handling, exact/perceptual groups, known entropy values, target
  budgets, image-comparison assets and all 13 version restores by SHA-256.
- Both PDF fixtures were rendered and inspected, including all brochure pages.

Still unverified: actual Mac double-click launcher execution, graphical app
layout/scrollbars, native Mac dialogs and Trash, .app/.dmg packaging. A headless
browser executable is unavailable in this runtime; DOM tests do not measure
pixel geometry. Previous Mac validation limits continue to apply.
