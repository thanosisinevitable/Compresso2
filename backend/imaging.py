"""Target Lock's bounded JPEG search and Artifact Lens image comparison."""
from pathlib import Path
import io
import math
import shutil
import numpy as np
from PIL import Image, ImageOps, ImageCms
from skimage.metrics import structural_similarity
from common import checked_file, fingerprint
from compressor import unique_name

IMAGE_TYPES = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.webp', '.bmp'}
PREVIEW_EDGE = 1600


def rgb_image(path):
    with Image.open(path) as opened:
        if getattr(opened, 'n_frames', 1) != 1:
            raise ValueError('Target Lock and Artifact Lens require a single-frame image. Export multipage or animated inputs first.')
        image = ImageOps.exif_transpose(opened)
        profile = image.info.get('icc_profile')
        alpha = image.convert('RGBA').getchannel('A') if image.mode in ('RGBA', 'LA') or 'transparency' in image.info else None
        if profile:
            try:
                image = ImageCms.profileToProfile(image.convert('RGB') if image.mode not in ('RGB','CMYK','LAB') else image,
                                                  ImageCms.ImageCmsProfile(io.BytesIO(profile)), ImageCms.createProfile('sRGB'), outputMode='RGB')
            except (OSError, ValueError, ImageCms.PyCMSError) as error:
                raise ValueError('The embedded color profile cannot be converted safely to sRGB.') from error
        else:
            image = image.convert('RGB')
        if alpha is not None:
            background = Image.new('RGB', image.size, 'white')
            background.paste(image, mask=alpha)
            image = background
        return image.copy()


def search_jpeg(image, directory, target, job):
    """Search qualities 1–95; every chosen result is checked against the byte limit."""
    best, smallest, trace = None, None, []
    cache = {}
    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    def evaluate(quality):
        nonlocal best, smallest
        if quality in cache:
            return cache[quality]
        job.check()
        dest = directory / f'q{quality}.jpg'
        image.save(dest, 'JPEG', quality=quality, optimize=True, progressive=True, icc_profile=icc)
        length = dest.stat().st_size
        trace.append({'quality': quality, 'bytes': length, 'width': image.width, 'height': image.height})
        cache[quality] = length
        candidate = {'path': dest, 'quality': quality, 'size': length}
        if smallest is None or length < smallest['size']:
            smallest = candidate
        if length <= target and (best is None or quality > best['quality']):
            best = candidate
        return length
    if evaluate(95) <= target:
        return best, smallest, trace
    if evaluate(1) > target:
        return best, smallest, trace
    low, high = 2, 94
    while low <= high:
        mid = (low + high) // 2
        if evaluate(mid) <= target:
            low = mid + 1
        else:
            high = mid - 1
    for quality in range(max(1, best['quality'] - 1), min(95, best['quality'] + 3) + 1):
        evaluate(quality)
    return best, smallest, trace


def target_lock(paths, options, job):
    target = options.get('targetBytes')
    resize = options.get('allowResize', False)
    if type(target) is not int or not 1024 <= target <= 100 * 1024**2 or type(resize) is not bool:
        raise ValueError('Set a target from 1 KiB to 100 MiB and choose whether resizing is allowed.')
    if not 1 <= len(paths) <= 100:
        raise ValueError('Choose between 1 and 100 images.')
    sources = [checked_file(p) for p in dict.fromkeys(paths)]
    if any(p.suffix.lower() not in IMAGE_TYPES for p in sources):
        raise ValueError('Target Lock accepts PNG, JPG, TIFF, WebP and BMP images; PDF and ZIP are not supported here.')
    snapshots = {str(p): fingerprint(p) for p in sources}
    rows, outputs, pairs, used = [], [], [], set()
    for index, src in enumerate(sources):
        job.progress(f'Target Lock · {src.name}', index, len(sources))
        directory = job.directory / str(index)
        directory.mkdir()
        image = rgb_image(src)
        original_size = image.size
        name = unique_name(src.stem + '.jpg', used)
        trace, chosen, smallest = [], None, None
        if src.suffix.lower() in {'.jpg', '.jpeg'} and snapshots[str(src)][2] <= target:
            chosen = {'path': directory / 'original.jpg', 'quality': None, 'size': snapshots[str(src)][2]}
            shutil.copyfile(src, chosen['path'])
        else:
            for step in range(16):
                job.check()
                attempt = directory / f'scale-{step}'
                attempt.mkdir()
                best, minimum, history = search_jpeg(image, attempt, target, job)
                trace.extend(history)
                smallest = minimum
                if best:
                    chosen = best
                    break
                if not resize or min(image.size) <= 32:
                    break
                scale = min(.85, math.sqrt(target / max(1, minimum['size'])) * .9)
                new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
                if min(new_size) < 16:
                    break
                image = image.resize(new_size, Image.Resampling.LANCZOS)
        if fingerprint(src) != snapshots[str(src)]:
            raise ValueError(f'{src.name} changed during processing. Please retry.')
        row = {'name': src.name, 'inputBytes': snapshots[str(src)][2], 'targetBytes': target,
               'met': chosen is not None, 'quality': chosen['quality'] if chosen else None,
               'outputBytes': chosen['size'] if chosen else None, 'width': image.width,
               'height': image.height, 'originalWidth': original_size[0], 'originalHeight': original_size[1],
               'resized': image.size != original_size, 'attempts': trace,
               'smallestAttemptBytes': smallest['size'] if smallest else None}
        if chosen:
            assert chosen['path'].stat().st_size <= target
            outputs.append((chosen['path'], name))
            row['lensIndex'] = len(pairs)
            pairs.append({'name': name, 'source': str(src), 'output': str(chosen['path']), 'identity': [str(n) for n in snapshots[str(src)]]})
        rows.append(row)
    for src in sources:
        if fingerprint(src) != snapshots[str(src)]:
            raise ValueError('An input changed during processing. Please retry.')
    artifact, name = None, None
    if len(outputs) == 1:
        artifact, name = outputs[0]
    elif outputs:
        import zipfile
        artifact, name = job.directory / 'target-locked.zip', 'target-locked.zip'
        with zipfile.ZipFile(artifact, 'w', zipfile.ZIP_STORED, allowZip64=True) as archive:
            for output, output_name in outputs:
                with output.open('rb') as reader, archive.open(output_name, 'w', force_zip64=True) as writer:
                    while block := reader.read(1024 * 1024):
                        job.check()
                        writer.write(block)
    return {'artifact': str(artifact) if artifact else None, 'name': name, 'sources': [str(p) for p in sources],
            'rows': rows, 'lensPairs': pairs, 'successCount': len(outputs), 'failedCount': len(rows) - len(outputs),
            'outputBytes': artifact.stat().st_size if artifact else 0, 'inputBytes': sum(r['inputBytes'] for r in rows)}


def compare(paths, options, job):
    source, output = [checked_file(p) for p in paths]
    before = [fingerprint(p) for p in (source, output)]
    if options.get('identity') and [str(n) for n in before[0]] != [str(n) for n in options['identity']]:
        raise ValueError('The original changed since compression. Reprocess it before comparing.')
    job.progress('Normalizing image orientation and color')
    original, compressed = rgb_image(source), rgb_image(output)
    original_size, output_size = original.size, compressed.size
    resized = original_size != output_size
    # Match dimensions explicitly, then bound metric and preview memory. No full-file float arrays.
    compressed.thumbnail((PREVIEW_EDGE, PREVIEW_EDGE), Image.Resampling.LANCZOS)
    original = original.resize(compressed.size, Image.Resampling.LANCZOS)
    job.check()
    left, right = np.asarray(original), np.asarray(compressed)
    job.progress('Measuring structural similarity')
    if min(compressed.size) >= 7:
        score = float(structural_similarity(left, right, channel_axis=2, data_range=255))
    else:
        score = 1.0 if np.array_equal(left, right) else None
    delta = np.abs(left.astype(np.int16) - right.astype(np.int16)).astype(np.float32)
    error = delta.mean(axis=2)
    mse = float(np.mean((left.astype(np.float32) - right.astype(np.float32))**2))
    mean_error = float(error.mean())
    gain = options.get('gain', 8)
    if type(gain) is not int or not 1 <= gain <= 32:
        raise ValueError('Difference amplification must be from 1 to 32.')
    strength = np.minimum(1, error / 255 * gain)
    heat = np.stack([strength * 255, np.sqrt(strength) * 180, strength**3 * 50], axis=2).astype(np.uint8)
    assets = {}
    for key, image in [('original', original), ('compressed', compressed), ('difference', Image.fromarray(np.clip(delta*gain,0,255).astype(np.uint8))), ('heatmap',Image.fromarray(heat))]:
        job.check()
        destination = job.directory / f'{key}.png'
        image.save(destination, 'PNG')
        assets[key] = str(destination)
    if [fingerprint(p) for p in (source, output)] != before:
        raise ValueError('An image changed while comparing. Please retry.')
    return {'assets': assets, 'name': source.name, 'ssim': score, 'meanAbsoluteError': mean_error,
            'psnr': 10 * math.log10(255**2 / mse) if mse else None, 'identicalPreview': mse == 0,
            'originalWidth': original_size[0], 'originalHeight': original_size[1],
            'outputWidth': output_size[0], 'outputHeight': output_size[1], 'resized': resized,
            'previewWidth': compressed.width, 'previewHeight': compressed.height,
            'previewEdge': PREVIEW_EDGE, 'gain': gain,
            'inputBytes': source.stat().st_size, 'outputBytes': output.stat().st_size}
