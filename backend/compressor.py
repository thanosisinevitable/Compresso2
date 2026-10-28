"""Streaming file workflows. Inputs are never overwritten."""
from pathlib import Path, PurePosixPath
import os
import shutil
import stat
import subprocess
import time
import zipfile
from PIL import Image, ImageOps, ImageSequence
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from common import checked_file, fingerprint

SUPPORTED = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.pdf', '.webp', '.bmp'}
PRESETS = {'Extreme': 'screen', 'High': 'ebook', 'Medium': 'printer', 'Low': 'prepress'}
MAX_ZIP_BYTES = 10 * 1024**3
MAX_ZIP_FILES = 20000


def ghostscript():
    configured = os.environ.get('COMPRESSO_GS')
    return configured if configured and Path(configured).is_file() else shutil.which('gs')


def run_ghostscript(arguments, job):
    executable = ghostscript()
    if not executable:
        raise ValueError('Ghostscript is missing. In development, install it with brew install ghostscript, then restart Compresso.')
    command = [executable, *arguments]
    with open(job.directory / 'ghostscript.log', 'wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=log)
        started = time.monotonic()
        try:
            while process.poll() is None:
                job.check()
                if time.monotonic() - started > 600:
                    raise ValueError('PDF processing exceeded 10 minutes. Try a smaller document.')
                time.sleep(.1)
            if process.returncode != 0:
                raise ValueError('Could not process the PDF. It may be damaged or password-protected.')
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def compress_pdf(src, dst, quality, job):
    run_ghostscript(['-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.7',
                    f'-dPDFSETTINGS=/{PRESETS[quality]}', '-dDetectDuplicateImages=true',
                    '-dSubsetFonts=true', '-dCompressFonts=true', '-dSAFER',
                    '-dNOPAUSE', '-dQUIET', '-dBATCH', f'-sOutputFile={dst}', str(src)], job)
    if not dst.is_file() or not dst.stat().st_size:
        raise ValueError('Ghostscript did not produce a PDF.')
    return dst


def flatten_rgb(image):
    image = ImageOps.exif_transpose(image)
    if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
        rgba = image.convert('RGBA')
        background = Image.new('RGB', rgba.size, 'white')
        background.paste(rgba, mask=rgba.getchannel('A'))
        return background
    return image.convert('RGB')


def compress_file(src, dst, quality, job):
    ext = src.suffix.lower()
    if ext == '.pdf':
        compress_pdf(src, dst, quality, job)
    else:
        with Image.open(src) as image:
            job.check()
            if ext in {'.tif', '.tiff'}:
                image.save(dst, 'TIFF', save_all=True, compression='tiff_adobe_deflate')
            elif ext == '.png':
                image.save(dst, 'PNG', optimize=True, save_all=getattr(image, 'is_animated', False))
            elif ext == '.webp':
                image.save(dst, 'WEBP', lossless=True, exact=True, save_all=getattr(image, 'is_animated', False))
            elif ext == '.bmp':
                image.save(dst, 'BMP')
            else:
                rgb = flatten_rgb(image)
                rgb.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
                rgb.save(dst, 'JPEG', quality=75, optimize=True, progressive=True,
                         icc_profile=image.info.get('icc_profile'))
    job.check()
    if dst.stat().st_size >= src.stat().st_size:
        shutil.copyfile(src, dst)
        return False
    return True


def extract_zip(src, directory, job):
    inputs, skipped, written = [], 0, 0
    with zipfile.ZipFile(src) as archive:
        members = archive.infolist()
        if len(members) > MAX_ZIP_FILES or sum(i.file_size for i in members) > MAX_ZIP_BYTES:
            raise ValueError('ZIP exceeds the safety limit: 20,000 entries or 10 GiB expanded.')
        for index, info in enumerate(members):
            job.check()
            relative = PurePosixPath(info.filename.replace('\\', '/'))
            mode = info.external_attr >> 16
            if relative.is_absolute() or '..' in relative.parts or any(':' in p for p in relative.parts) or stat.S_ISLNK(mode):
                raise ValueError('ZIP contains an unsafe path or symbolic link.')
            if info.is_dir() or any(p.startswith('.') or p == '__MACOSX' for p in relative.parts) or relative.suffix.lower() not in SUPPORTED:
                skipped += not info.is_dir()
                continue
            target = directory / str(index) / relative.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as reader, target.open('wb') as writer:
                while block := reader.read(1024 * 1024):
                    job.check()
                    written += len(block)
                    if written > MAX_ZIP_BYTES:
                        raise ValueError('ZIP expanded beyond the 10 GiB safety limit.')
                    writer.write(block)
            inputs.append((target, str(relative)))
            job.progress('Opening archive', index + 1, len(members))
    return inputs, int(skipped)


def unique_name(name, used):
    name = PurePosixPath(name)
    candidate, counter = str(name), 2
    while candidate.casefold() in used:
        candidate = str(name.with_name(f'{name.stem} ({counter}){name.suffix}'))
        counter += 1
    used.add(candidate.casefold())
    return candidate


def compress(paths, options, job):
    job.check()
    if not paths or len(paths) > MAX_ZIP_FILES:
        raise ValueError('Choose between 1 and 20,000 files.')
    sources = [checked_file(p) for p in dict.fromkeys(paths)]
    snapshots = {str(p): fingerprint(p) for p in sources}
    zipped = len(sources) == 1 and sources[0].suffix.lower() == '.zip'
    if any(p.suffix.lower() == '.zip' for p in sources) and not zipped:
        raise ValueError('Choose one ZIP archive at a time, or select individual files.')
    if zipped:
        inputs, skipped = extract_zip(sources[0], job.directory / 'input', job)
    else:
        inputs, skipped = [(p, p.name) for p in sources], 0
    if not inputs:
        raise ValueError('No supported files found. Use PNG, JPG, JPEG, TIF, TIFF, WebP, BMP or PDF.')
    if any(p.suffix.lower() not in SUPPORTED for p, _ in inputs):
        raise ValueError('Supported compression formats: PNG, JPG, JPEG, TIF, TIFF, WebP, BMP and PDF; ZIP may contain these formats.')
    quality = options.get('pdfQuality', 'Extreme')
    tiff = options.get('tiffMode', 'keep')
    format = options.get('outputFormat', 'original')
    if format not in {'original', 'png', 'jpg', 'tiff', 'webp', 'bmp', 'pdf'}:
        raise ValueError('Choose Original, PNG, JPG, TIFF, WebP, BMP or PDF output.')
    if format != 'original' and (type(options.get('pdfDpi', 150)) is not int or options.get('pdfDpi', 150) not in {72, 150, 300}):
        raise ValueError('PDF image resolution must be 72, 150 or 300 dpi.')
    if quality not in PRESETS or tiff not in {'keep', 'jpg', 'pdf'}:
        raise ValueError('Invalid compression option.')
    output = job.directory / 'output'
    output.mkdir()
    outputs, used, unchanged = [], set(), 0
    lens_pairs = []
    def add_lens_pair(src, dest, name):
        if len(lens_pairs) >= 50:
            return
        with Image.open(src) as image:
            if getattr(image, 'n_frames', 1) != 1:
                return
        with Image.open(dest) as image:
            if getattr(image, 'n_frames', 1) != 1:
                return
        lens_pairs.append({'name': name, 'source': str(src), 'output': str(dest),
                           'identity': [str(n) for n in fingerprint(src)]})
    original_bytes = sum(p.stat().st_size for p, _ in inputs)
    if format != 'original':
        from converter import convert_inputs
        outputs = convert_inputs(inputs, format, options.get('pdfDpi', 150), quality, job, output, used, add_lens_pair)
    else:
        tiffs = [(p, name) for p, name in inputs if p.suffix.lower() in {'.tif', '.tiff'}]
        if tiff == 'pdf' and tiffs:
            target = output / 'tiff-converted.pdf'
            page_directory = job.directory / 'pdf-pages'
            page_directory.mkdir()
            page_paths = []
            for index, (src, _) in enumerate(tiffs):
                job.progress('Converting TIFF pages to PDF', index, len(tiffs))
                with Image.open(src) as image:
                    for frame in ImageSequence.Iterator(image):
                        job.check()
                        rgb = flatten_rgb(frame)
                        dpi = frame.info.get('dpi', (72, 72))
                        dx, dy = [min(1200, max(36, float(v or 72))) for v in dpi]
                        width, height = rgb.width * 72 / dx, rgb.height * 72 / dy
                        # One canvas per page avoids accumulating the whole TIFF's PDF image data in RAM.
                        page_path = page_directory / f'{len(page_paths):08}.pdf'
                        document = canvas.Canvas(str(page_path), pagesize=(width,height), pageCompression=1)
                        document.drawImage(ImageReader(rgb), 0, 0, width, height)
                        document.showPage()
                        document.save()
                        page_paths.append(page_path)
            if len(page_paths) == 1:
                shutil.copyfile(page_paths[0], target)
            else:
                arguments = job.directory / 'pdf-pages.args'
                # Ghostscript's response file avoids the OS command-line length limit.
                arguments.write_text('\n'.join('"' + str(p).replace('\\','\\\\').replace('"','\\"') + '"' for p in page_paths) + '\n')
                run_ghostscript(['-dSAFER', '-dBATCH', '-dNOPAUSE', '-dQUIET', '-sDEVICE=pdfwrite',
                                '-dAutoRotatePages=/None', '-dAutoFilterColorImages=false',
                                '-dColorImageFilter=/FlateEncode', '-dAutoFilterGrayImages=false',
                                '-dGrayImageFilter=/FlateEncode', f'-sOutputFile={target}', '@' + str(arguments)], job)
            if not target.is_file() or not target.stat().st_size:
                raise ValueError('TIFF conversion did not produce a PDF.')
            outputs.append((target, unique_name(tiffs[0][0].stem + '.pdf', used)))
        for index, (src, name) in enumerate(inputs):
            job.check()
            job.progress(f'Processing {src.name}', index, len(inputs))
            ext = src.suffix.lower()
            if ext in {'.tif', '.tiff'} and tiff == 'pdf':
                continue
            dest_dir = output / str(index)
            dest_dir.mkdir()
            if ext in {'.tif', '.tiff'} and tiff == 'jpg':
                with Image.open(src) as image:
                    count = image.n_frames
                    for page, frame in enumerate(ImageSequence.Iterator(image)):
                        job.check()
                        suffix = f'-page-{page + 1:03}' if count > 1 else ''
                        archive_name = str(PurePosixPath(name).with_suffix('')) + suffix + '.jpg'
                        dest = dest_dir / (src.stem + suffix + '.jpg')
                        flatten_rgb(frame).save(dest, 'JPEG', quality=85, optimize=True, progressive=True)
                        outputs.append((dest, unique_name(archive_name, used)))
                        if count == 1:
                            add_lens_pair(src, dest, dest.name)
            else:
                dest = dest_dir / src.name
                reduced = compress_file(src, dest, quality, job)
                unchanged += not reduced
                outputs.append((dest, unique_name(name, used)))
                if ext in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.webp', '.bmp'}:
                    add_lens_pair(src, dest, dest.name)
    for src in sources:
        if fingerprint(src) != snapshots[str(src)]:
            raise ValueError(f'{src.name} changed during processing. Please retry.')
    if len(outputs) == 1 and not zipped and len(sources) == 1:
        artifact, name = outputs[0]
        name = PurePosixPath(name).name
    else:
        artifact, name = job.directory / 'compressed.zip', 'compressed.zip'
        with zipfile.ZipFile(artifact, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for src, arcname in outputs:
                job.check()
                with src.open('rb') as reader, archive.open(arcname, 'w', force_zip64=True) as writer:
                    while block := reader.read(1024 * 1024):
                        job.check()
                        writer.write(block)
    job.progress('Ready to save', 1, 1)
    return {'artifact': str(artifact), 'name': name, 'inputBytes': original_bytes,
            'sourceBytes': sum(p.stat().st_size for p in sources), 'outputBytes': artifact.stat().st_size,
            'inputCount': len(inputs), 'outputCount': len(outputs), 'skipped': skipped,
            'unchanged': unchanged, 'outputFormat': format, 'lensPairs': lens_pairs, 'sources': [str(p) for p in sources]}
