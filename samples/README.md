# Sample walkthrough

64 synthetic demo files for Compresso 2.2. Select files from this folder in the
app; keep generated results in the repository's ignored `outputs/` folder.
Use a disposable copy of the Ghost Hunt folder when demonstrating Trash.

| Feature | Choose | Suggested action |
| --- | --- | --- |
| Compression | [Image-rich PDF](01_Compress/06_image-rich-brochure.pdf) | Standard > **Keep original** > **Extreme** > Compress files. Save and compare sizes. |
| Transparency | [PNG badge](01_Compress/02_transparent-badge.png) | Compress in the original format; transparency stays. |
| Image conversion | [Studio PNG](01_Compress/01_studio-unoptimized.png) | Choose JPG, TIFF, WebP, BMP or PDF under **Convert to**. |
| Multipage conversion | [Three-page TIFF](01_Compress/05_three-page-contact-sheet.tiff) | Convert to PDF or TIFF to retain pages in one document; JPG/PNG create three images in a ZIP. |
| PDF page export | [Image-rich PDF](01_Compress/06_image-rich-brochure.pdf) | Convert to PNG/JPG at 150 dpi; all three pages are exported. |
| ZIP processing | [Mixed ZIP](01_Compress/09_mixed-batch.zip) | Compress or convert its contents. Two unsupported/hidden entries are intentionally skipped. |
| Exact/visual duplicates | [02_Ghost_Hunt](02_Ghost_Hunt/) | Scan this folder only, enable visual matching, use threshold **8**. Expect **3 exact groups + 2 visual groups**. Preview before cleanup. |
| Entropy heatmap | [Four-section file](03_Entropy_Lab/06_four-section-heatmap.bin) | Open in Entropy Lab. Hover across zero, alternating, cycling and noisy regions. |
| Known entropy | [03_Entropy_Lab](03_Entropy_Lab/) | Files 01-04 produce exactly **0, 1, 2 and 8 bits/byte**. File 00 is empty. |
| Version storage | [Shared_Binary](04_Version_Vault/Shared_Binary/) | Select all five files, order v01-v05, build and save a vault. Open it and restore one/all versions. |
| Instant restoration | [Ready-made vault](04_Version_Vault/Ready_To_Open/campaign-demo.cvault) | Version Vault > **Open & restore**. Recover any of its five source files. |
| Size targeting | [Studio master](05_Target_Lock/01_studio-master.png) | Target Lock > **128 KiB**, resizing off > Lock target. |
| Constraint failure | [Noise stress image](05_Target_Lock/05_fine-noise-stress.png) | Try **1 KiB**, resizing off; then **8 KiB**, resizing on. |
| Artifact inspection | [High-quality detail chart](06_Artifact_Lens/02_detail-chart-high-quality.jpg) | Standard compression > **Inspect image**. Try split, zoom, Difference and Heatmap. |

**Extra vault sequences:** `Design_TIFF/` changes a caption, `Text_Revisions/`
changes production notes, and `Unrelated_Fallback/` demonstrates archive
overhead for unrelated data. Select the files inside one sequence folder.

**Entropy talking point:** `04_uniform-cycle-8-bits.bin` has maximum byte entropy
but a repeating sequence; it still compresses well. Byte entropy ignores order.

**Target Lock batch:** choose files 01, 02, 03, 04, 06 and 07 from
`05_Target_Lock/` at 128 KiB with resizing off. All six fitted in the verified run.

**Artifact Lens:** opens from actual app results. The pre-encoded Q10/resized
images are manual reference files, not a separate pair-loading interface.
SSIM is a structural metric, not a percentage of visual quality retained.

Measured Linux baseline results are in [EXPECTED_RESULTS.json](EXPECTED_RESULTS.json).
Exact encoded sizes can vary by platform and encoder version. Supported document
input is PDF; Word DOC/DOCX conversion is not included.

To verify the original fixtures on macOS, run from the project root:

```bash
cd samples
shasum -a 256 -c SHA256SUMS.txt
```

Checksums exclude the checksum file itself. Git attributes preserve fixture
bytes across checkouts. All sample imagery and byte data are synthetic.
