from pathlib import Path
import zipfile
import shutil
import numpy as np
import pytest
from PIL import Image
from reportlab.pdfgen import canvas
from pypdf import PdfReader
from compressor import compress
from common import Cancelled, checked_file
from imaging import compare
from conftest import TestJob as JobFixture


def source_at(directory, extension):
    path = directory / ('source.' + extension)
    if extension == 'pdf':
        document = canvas.Canvas(str(path), pagesize=(120, 80))
        document.drawString(10, 40, 'First page')
        document.showPage()
        document.setPageSize((80, 120))
        document.drawString(10, 40, 'Second page')
        document.showPage()
        document.save()
    else:
        first = Image.new('RGB', (80, 60), '#3492ae')
        if extension == 'tiff':
            first.save(path, save_all=True, append_images=[Image.new('RGB', (40, 70), '#cd4780')])
        else:
            first.save(path)
    return path


@pytest.mark.parametrize('source_format', ['png', 'jpg', 'tiff', 'webp', 'bmp', 'pdf'])
@pytest.mark.parametrize('destination_format', ['png', 'jpg', 'tiff', 'webp', 'bmp', 'pdf'])
def test_conversion_matrix_keeps_pages_and_correct_encoding(tmp_path, job, source_format, destination_format):
    if source_format == 'pdf' and not shutil.which('gs'):
        pytest.skip('PDF rendering requires Ghostscript')
    source = source_at(tmp_path, source_format)
    original = source.read_bytes()
    count = 2 if source_format in {'tiff', 'pdf'} else 1
    result = compress([str(source)], {'outputFormat': destination_format, 'pdfDpi': 72}, job)
    assert source.read_bytes() == original
    if destination_format == 'pdf':
        assert result['name'] == 'source.pdf'
        assert len(PdfReader(result['artifact']).pages) == count
    elif destination_format == 'tiff':
        assert result['name'] == 'source.tiff'
        with Image.open(result['artifact']) as image:
            assert image.format == 'TIFF' and image.n_frames == count
            assert image.size == ((120, 80) if source_format == 'pdf' else (80, 60))
            if count == 2:
                image.seek(1)
                assert image.size == ((80, 120) if source_format == 'pdf' else (40, 70))
    else:
        expected = {'png': 'PNG', 'jpg': 'JPEG', 'webp': 'WEBP', 'bmp': 'BMP'}[destination_format]
        if count == 1:
            assert result['name'] == f'source.{destination_format}'
            with Image.open(result['artifact']) as image:
                assert image.format == expected and image.size == (80, 60)
        else:
            with zipfile.ZipFile(result['artifact']) as archive:
                assert archive.namelist() == [f'source-page-001.{destination_format}', f'source-page-002.{destination_format}']
                for name in archive.namelist():
                    with archive.open(name) as reader, Image.open(reader) as image:
                        assert image.format == expected
    if source_format not in {'tiff', 'pdf'} and destination_format != 'pdf':
        assert len(result['lensPairs']) == 1


@pytest.mark.parametrize('destination', ['png', 'tiff', 'webp'])
def test_conversion_preserves_transparent_pixels(tmp_path, job, destination):
    source = tmp_path / 'transparent.png'
    image = Image.new('RGBA', (30, 20), (71, 119, 201, 80))
    image.putpixel((0, 0), (91, 37, 221, 0))
    image.save(source)
    result = compress([str(source)], {'outputFormat': destination}, job)
    with Image.open(result['artifact']) as output:
        assert np.array_equal(np.asarray(output.convert('RGBA')), np.asarray(image))


@pytest.mark.parametrize('destination', ['jpg', 'bmp'])
def test_opaque_conversion_flattens_alpha_on_white(tmp_path, job, destination):
    source = tmp_path / 'alpha.png'
    Image.new('RGBA', (30, 20), (0, 0, 0, 0)).save(source)
    result = compress([str(source)], {'outputFormat': destination}, job)
    with Image.open(result['artifact']) as output:
        assert output.convert('RGB').getpixel((0, 0)) == (255, 255, 255)


@pytest.mark.parametrize('destination', ['png', 'tiff'])
def test_conversion_keeps_16_bit_grayscale(tmp_path, job, destination):
    source = tmp_path / 'depth.tiff'
    values = np.array([[0, 255, 256, 65535], [42000, 1, 512, 32768]], dtype=np.uint16)
    Image.fromarray(values).save(source)
    result = compress([str(source)], {'outputFormat': destination}, job)
    with Image.open(result['artifact']) as output:
        assert np.array_equal(np.asarray(output), values)


def test_pdf_resolution_and_original_unchanged(tmp_path, job):
    source = source_at(tmp_path, 'pdf')
    result = compress([str(source)], {'outputFormat': 'png', 'pdfDpi': 150}, job)
    with zipfile.ZipFile(result['artifact']) as archive, archive.open('source-page-001.png') as reader, Image.open(reader) as image:
        assert image.size == (250, 167)


def test_conversion_applies_exif_rotation(tmp_path, job):
    source = tmp_path / 'rotated.jpg'
    exif = Image.Exif()
    exif[274] = 6
    Image.new('RGB', (80, 60), 'red').save(source, exif=exif)
    result = compress([str(source)], {'outputFormat': 'png'}, job)
    with Image.open(result['artifact']) as output:
        assert output.size == (60, 80) and output.getexif().get(274, 1) == 1


def test_conversion_does_not_clip_32_bit_values_silently(tmp_path, job):
    source = tmp_path / 'signed.tiff'
    Image.fromarray(np.array([[-1, 100000]], dtype=np.int32)).save(source)
    with pytest.raises(ValueError, match='16-bit'):
        compress([str(source)], {'outputFormat': 'png'}, job)


@pytest.mark.parametrize('destination', ['png', 'tiff', 'pdf'])
def test_animation_conversion_exports_every_frame(tmp_path, job, destination):
    source = tmp_path / 'animated.png'
    frames = [Image.new('RGB', (20, 15), color) for color in ['red', 'green', 'blue']]
    frames[0].save(source, save_all=True, append_images=frames[1:], duration=100, loop=0)
    result = compress([str(source)], {'outputFormat': destination}, job)
    if destination == 'png':
        with zipfile.ZipFile(result['artifact']) as archive:
            assert len(archive.namelist()) == 3
            for index, name in enumerate(archive.namelist()):
                with archive.open(name) as reader, Image.open(reader) as image:
                    assert image.convert('RGB').getpixel((0, 0)) == frames[index].getpixel((0, 0))
    elif destination == 'tiff':
        with Image.open(result['artifact']) as image:
            assert image.n_frames == 3
    else:
        assert len(PdfReader(result['artifact']).pages) == 3


def test_conversion_zip_preserves_folders_and_collision_names(tmp_path, job):
    source = source_at(tmp_path, 'png')
    second = source_at(tmp_path, 'jpg')
    bundle = tmp_path / 'input.zip'
    with zipfile.ZipFile(bundle, 'w') as archive:
        archive.write(source, 'a/source.png')
        archive.write(second, 'a/source.jpg')
        archive.write(source, 'b/source.png')
    result = compress([str(bundle)], {'outputFormat': 'webp'}, job)
    with zipfile.ZipFile(result['artifact']) as archive:
        assert archive.namelist() == ['a/source.webp', 'a/source (2).webp', 'b/source.webp']


def test_conversion_validates_choices_and_cancellation(tmp_path, job):
    source = source_at(tmp_path, 'png')
    with pytest.raises(ValueError, match='output'):
        compress([str(source)], {'outputFormat': 'docx'}, job)
    with pytest.raises(ValueError, match='resolution'):
        compress([str(source)], {'outputFormat': 'png', 'pdfDpi': 900}, job)
    job.cancelled.set()
    with pytest.raises(Cancelled):
        compress([str(source)], {'outputFormat': 'png'}, job)


@pytest.mark.parametrize('zipped', [False, True])
def test_mac_style_temp_alias_resolves_for_lens(tmp_path, monkeypatch, zipped):
    import main
    real = tmp_path / 'private-var'
    real.mkdir()
    alias = tmp_path / 'var'
    alias.symlink_to(real, target_is_directory=True)
    actual = real / 'compresso-job'
    actual.mkdir()
    monkeypatch.setattr(main.tempfile, 'mkdtemp', lambda **_options: str(alias / actual.name))
    job = main.Job('compress')
    assert job.directory == actual.resolve()
    source = source_at(tmp_path, 'png')
    selected = source
    if zipped:
        selected = tmp_path / 'archive.zip'
        with zipfile.ZipFile(selected, 'w') as archive:
            archive.write(source, 'images/source.png')
    result = compress([str(selected)], {}, job)
    pair = result['lensPairs'][0]
    assert checked_file(pair['output']) == Path(pair['output'])
    comparison_dir = real / 'comparison'
    comparison_dir.mkdir()
    compared = compare([pair['source'], pair['output']], {'identity': pair['identity']}, JobFixture(comparison_dir))
    assert compared['ssim'] == 1
    # The fix doesn't permit user-selected leaf symlinks.
    linked = tmp_path / 'linked.png'
    linked.symlink_to(source)
    with pytest.raises(ValueError, match='symbolic'):
        checked_file(linked)


@pytest.mark.parametrize('format', ['webp', 'bmp'])
def test_original_mode_keeps_new_input_formats(tmp_path, job, format):
    source = source_at(tmp_path, format)
    result = compress([str(source)], {}, job)
    assert result['name'] == source.name
    with Image.open(result['artifact']) as image:
        assert image.format == format.upper()
