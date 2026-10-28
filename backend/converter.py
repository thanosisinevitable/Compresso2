"""Explicit image/PDF conversions; every page is retained, originals untouched."""
from pathlib import Path, PurePosixPath
import shutil
from PIL import Image, ImageOps, ImageCms, TiffImagePlugin
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from compressor import run_ghostscript, compress_pdf, unique_name

FORMATS = {'png': 'PNG', 'jpg': 'JPEG', 'tiff': 'TIFF', 'webp': 'WEBP', 'bmp': 'BMP'}
MAX_PAGES = 2000


def prepared_frame(image, output_format):
    frame = ImageOps.exif_transpose(image)
    # Preserve high-depth grayscale when the destination can represent it.
    if frame.mode in {'I;16', 'I;16L', 'I;16B', 'I', 'F'} and output_format in {'png', 'tiff'}:
        if output_format == 'png' and frame.mode == 'F':
            raise ValueError('Floating-point images require TIFF output; PNG cannot preserve their values.')
        if output_format == 'png' and frame.mode in {'I;16B', 'I;16L'}:
            return frame.convert('I;16')
        if output_format == 'png' and frame.mode == 'I':
            minimum, maximum = frame.getextrema()
            if minimum < 0 or maximum > 65535:
                raise ValueError('PNG supports at most 16-bit unsigned grayscale. Choose TIFF to retain these values.')
            return frame.convert('I;16')
        return frame.copy()
    alpha = frame.convert('RGBA').getchannel('A') if frame.mode in {'RGBA', 'LA'} or 'transparency' in frame.info else None
    profile = frame.info.get('icc_profile')
    if profile:
        import io
        try:
            frame = ImageCms.profileToProfile(frame.convert('RGB') if frame.mode not in {'RGB', 'CMYK', 'LAB'} else frame,
                ImageCms.ImageCmsProfile(io.BytesIO(profile)), ImageCms.createProfile('sRGB'), outputMode='RGB')
        except (OSError, ValueError, ImageCms.PyCMSError) as error:
            raise ValueError('The embedded color profile cannot be converted safely to sRGB.') from error
    else:
        frame = frame.convert('RGB')
    if alpha is not None:
        if output_format in {'png', 'webp', 'tiff'}:
            frame.putalpha(alpha)
        else:
            white = Image.new('RGB', frame.size, 'white')
            white.paste(frame, mask=alpha)
            frame = white
    # Carry only a profile describing the pixels actually written.
    frame.info.clear()
    frame.info['icc_profile'] = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    return frame


def pages_for(source, directory, dpi, job):
    """Yield one owned frame at a time; PDF rasterization uses bundled Ghostscript."""
    if source.suffix.lower() == '.pdf':
        directory.mkdir()
        run_ghostscript(['-dSAFER', '-dBATCH', '-dNOPAUSE', '-dQUIET', '-sDEVICE=pngalpha',
            '-dTextAlphaBits=4', '-dGraphicsAlphaBits=4', f'-r{dpi}', f'-dLastPage={MAX_PAGES + 1}',
            f'-sOutputFile={directory / "page-%06d.png"}', str(source)], job)
        paths = sorted(directory.glob('page-*.png'))
        if not paths:
            raise ValueError('The PDF has no renderable pages.')
        if len(paths) > MAX_PAGES:
            raise ValueError(f'Conversion supports at most {MAX_PAGES} pages per document.')
        for index, path in enumerate(paths):
            job.check()
            with Image.open(path) as image:
                frame = image.copy()
                frame.info['dpi'] = (dpi, dpi)
                try:
                    yield index, len(paths), frame
                finally:
                    frame.close()
    else:
        with Image.open(source) as image:
            count = getattr(image, 'n_frames', 1)
            if count > MAX_PAGES:
                raise ValueError(f'Conversion supports at most {MAX_PAGES} pages/frames per file.')
            for index in range(count):
                job.check()
                image.seek(index)
                frame = image.copy()
                try:
                    yield index, count, frame
                finally:
                    frame.close()


def write_image(frame, destination, format):
    options = {'icc_profile': frame.info.get('icc_profile')}
    if format == 'png':
        frame.save(destination, 'PNG', optimize=True, **options)
    elif format == 'jpg':
        frame.save(destination, 'JPEG', quality=85, optimize=True, progressive=True, **options)
    elif format == 'webp':
        frame.save(destination, 'WEBP', lossless=True, exact=True, method=4, **options)
    elif format == 'bmp':
        frame.save(destination, 'BMP')
    else:
        raise ValueError('Unsupported image destination.')


def image_pdf(source, directory, destination, dpi, job):
    directory.mkdir()
    page_paths = []
    for index, count, frame in pages_for(source, directory / 'raster', dpi, job):
        job.progress(f'Creating PDF · {source.name} · page {index + 1}/{count}')
        rgb = prepared_frame(frame, 'pdf')
        try:
            density = frame.info.get('dpi', (72, 72))
            if not isinstance(density, (tuple, list)) or len(density) < 2:
                density = (72, 72)
            dx, dy = [min(1200, max(36, float(v or 72))) for v in density[:2]]
            width, height = rgb.width * 72 / dx, rgb.height * 72 / dy
            page = directory / f'{index:06}.pdf'
            document = canvas.Canvas(str(page), pagesize=(width, height), pageCompression=1)
            document.drawImage(ImageReader(rgb), 0, 0, width, height)
            document.showPage()
            document.save()
            page_paths.append(page)
        finally:
            rgb.close()
    if len(page_paths) == 1:
        shutil.copyfile(page_paths[0], destination)
    else:
        arguments = directory / 'pages.args'
        arguments.write_text('\n'.join('"' + str(p).replace('\\', '\\\\').replace('"', '\\"') + '"' for p in page_paths) + '\n')
        run_ghostscript(['-dSAFER', '-dBATCH', '-dNOPAUSE', '-dQUIET', '-sDEVICE=pdfwrite',
            '-dAutoRotatePages=/None', '-dAutoFilterColorImages=false', '-dColorImageFilter=/FlateEncode',
            '-dAutoFilterGrayImages=false', '-dGrayImageFilter=/FlateEncode', f'-sOutputFile={destination}', '@' + str(arguments)], job)


def convert_inputs(inputs, format, dpi, quality, job, output, used, add_lens_pair):
    if format not in {*FORMATS, 'pdf'}:
        raise ValueError('Choose PNG, JPG, TIFF, WebP, BMP or PDF.')
    if type(dpi) is not int or dpi not in {72, 150, 300}:
        raise ValueError('PDF image resolution must be 72, 150 or 300 dpi.')
    outputs = []
    for position, (source, name) in enumerate(inputs):
        job.check()
        directory = output / str(position)
        directory.mkdir()
        extension = '.' + format
        relative = str(PurePosixPath(name).with_suffix(extension))
        destination = directory / (source.stem + extension)
        if format == 'pdf':
            if source.suffix.lower() == '.pdf':
                compress_pdf(source, destination, quality, job)
                if destination.stat().st_size >= source.stat().st_size:
                    shutil.copyfile(source, destination)
            else:
                image_pdf(source, directory / 'pdf-pages', destination, dpi, job)
            outputs.append((destination, unique_name(relative, used)))
        elif format == 'tiff':
            # Append frames incrementally; don't decode every page into a list.
            with TiffImagePlugin.AppendingTiffWriter(str(destination), True) as writer:
                for index, count, frame in pages_for(source, directory / 'raster', dpi, job):
                    job.progress(f'Converting · {source.name} · page {index + 1}/{count}')
                    prepared = prepared_frame(frame, format)
                    try:
                        prepared.save(writer, 'TIFF', compression='tiff_adobe_deflate', icc_profile=prepared.info.get('icc_profile'))
                        writer.newFrame()
                    finally:
                        prepared.close()
            outputs.append((destination, unique_name(relative, used)))
            if source.suffix.lower() != '.pdf':
                add_lens_pair(source, destination, destination.name)
        else:
            for index, count, frame in pages_for(source, directory / 'raster', dpi, job):
                job.progress(f'Converting · {source.name} · page {index + 1}/{count}')
                suffix = f'-page-{index + 1:03}' if count > 1 else ''
                filename = source.stem + suffix + extension
                path = directory / filename
                prepared = prepared_frame(frame, format)
                try:
                    write_image(prepared, path, format)
                finally:
                    prepared.close()
                archive_name = str(PurePosixPath(name).with_name(filename))
                outputs.append((path, unique_name(archive_name, used)))
                if count == 1 and source.suffix.lower() != '.pdf':
                    add_lens_pair(source, path, filename)
        if len(outputs) > 20000:
            raise ValueError('Conversion produced more than 20,000 outputs. Use a smaller batch.')
    return outputs
