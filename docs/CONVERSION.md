# Compresso 2.2 conversion

In **Compress > Standard**, select your files, choose **Convert to**, then click
**Convert files**. Save the completed result. **Keep original**
retains the normal compression workflow.

Supported sources: PNG, JPG/JPEG, TIF/TIFF, WebP, BMP, PDF, or a ZIP containing
those formats. Choose one ZIP at a time. Supported destinations:

| Destination | Images | PDF source | Multipage/frame handling |
| --- | --- | --- | --- |
| PNG | Full-resolution PNG; transparency retained | Rendered PNG pages | One file per page/frame, returned in ZIP when needed |
| JPG | Full-resolution progressive JPEG, quality 85 | Rendered JPEG pages | One file per page/frame; alpha flattened on white |
| TIFF | Deflate TIFF; transparency retained | Rendered TIFF pages | All pages remain in one TIFF per input document |
| WebP | Lossless WebP; transparency retained | Rendered WebP pages | One file per page/frame |
| BMP | Uncompressed RGB BMP | Rendered BMP pages | One file per page/frame; alpha flattened on white |
| PDF | One PDF per source, retaining all image pages | PDF optimization using the selected preset | All pages retained; multiple source documents produce a ZIP |

This converts image files and PDF documents. It does not provide Word DOC/DOCX,
spreadsheet, presentation, OCR, or editable PDF-to-Word conversion. PDF-to-image
conversion rasterizes text and vector graphics. Choose 72, 150 or 300 dpi;
150 dpi is the default. Ghostscript is required for PDF rendering/optimization
and merging multiple generated PDF pages.

Conversions keep image dimensions except when rasterizing PDF pages according
to dpi. They preserve originals, but the outputs can be larger. JPEG is lossy.
Color images are normalized to sRGB; arbitrary original metadata is not copied.
16-bit grayscale is preserved for PNG/TIFF when representable. Unsupported
floating-point/signed ranges are rejected for PNG instead of silently clipped.
Animation frames are exported as pages/images rather than retaining animation
timing. Each input is limited to 2,000 pages/frames; a batch can yield up to
20,000 output files. ZIP path safeguards remain active.

Eligible single-frame image results offer **Inspect**. PDF sources and multipage
outputs do not offer Artifact Lens as if they were single photographs. Ordinary
PDF viewers can inspect PDF results; Finder/Quick Look can preview saved files.

## Artifact Lens path fix

The earlier backend compared paths with their resolved form. On macOS the OS's
temporary directory can contain the `/var` alias for `/private/var`. Internally
created regular images could therefore be rejected with the misleading
"not a symbolic link" message. Compresso now resolves each processing directory
when it is created. It keeps strict checks for actual file symlinks.

A regression test simulates that alias and successfully opens comparisons from
both individual-image and extracted-ZIP results. React workflows are also
exercised with an aliased temporary root. Actual native Mac execution still
requires a Mac check.

Quit the old application, extract Compresso 2.2, and open
`Start-Compresso.command` or run `./start`. Repeat compression/conversion before
opening Inspect; results created by an old/restarted backend cannot be reused.
