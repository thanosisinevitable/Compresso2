import hashlib
from pathlib import Path
import shutil
import zipfile
import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.pdfgen import canvas
import compressor
from compressor import compress
from common import Cancelled


def image(path, size=(600,400), mode='RGB'):
    im=Image.new(mode,size,(50,120,180,70) if mode=='RGBA' else (50,120,180))
    ImageDraw.Draw(im).ellipse((60,40,400,300),fill=(210,90,10,210) if mode=='RGBA' else (210,90,10))
    im.save(path)
    return im


def test_png_stays_png_and_preserves_alpha(tmp_path, job):
    src=tmp_path/'transparent.png'; original=image(src,mode='RGBA')
    before=src.read_bytes()
    result=compress([str(src)],{},job)
    output=Path(result['artifact'])
    assert result['name']=='transparent.png'
    with Image.open(output) as actual:
        assert actual.format=='PNG' and actual.mode=='RGBA'
        assert actual.tobytes()==original.tobytes()
    assert src.read_bytes()==before
    assert result['outputBytes']<=len(before)


def test_jpeg_dimensions_and_original_preserved(tmp_path, job):
    src=tmp_path/'photo.jpg';image(src,(3000,2200))
    before=hashlib.sha256(src.read_bytes()).hexdigest()
    result=compress([str(src)],{},job)
    assert hashlib.sha256(src.read_bytes()).hexdigest()==before
    with Image.open(result['artifact']) as output:
        assert output.format=='JPEG'
        if not result['unchanged']: assert max(output.size)<=1920


def multipage(path):
    first=Image.new('RGB',(50,40),'red'); second=Image.new('RGB',(80,60),'blue')
    first.save(path,'TIFF',save_all=True,append_images=[second])


def test_keep_tiff_preserves_every_page(tmp_path, job):
    src=tmp_path/'pages.tiff';multipage(src)
    result=compress([str(src)],{'tiffMode':'keep'},job)
    assert result['name'].endswith('.tiff')
    with Image.open(src) as original, Image.open(result['artifact']) as output:
        assert output.format=='TIFF' and output.n_frames==2
        for index in range(2):
            original.seek(index);output.seek(index)
            assert output.tobytes()==original.tobytes()


def test_tiff_to_jpg_exports_all_pages(tmp_path, job):
    src=tmp_path/'pages.tif';multipage(src)
    result=compress([str(src)],{'tiffMode':'jpg'},job)
    assert result['name']=='compressed.zip'
    with zipfile.ZipFile(result['artifact']) as archive:
        assert archive.namelist()==['pages-page-001.jpg','pages-page-002.jpg']
        with archive.open(archive.namelist()[1]) as stream:
            with Image.open(stream) as output: assert output.size==(80,60)


def test_tiff_to_pdf_merges_pages_in_order(tmp_path, job):
    src=tmp_path/'pages.tif';multipage(src)
    result=compress([str(src)],{'tiffMode':'pdf'},job)
    assert result['name']=='pages.pdf'
    assert len(PdfReader(result['artifact']).pages)==2


@pytest.mark.parametrize('quality',['Extreme','High','Medium','Low'])
def test_pdf_presets(tmp_path, job, quality):
    if not shutil.which('gs'): pytest.skip('Ghostscript not installed')
    src=tmp_path/'source.pdf'
    document=canvas.Canvas(str(src));document.drawString(30,100,'Compresso test');document.showPage();document.save()
    before=src.read_bytes()
    result=compress([str(src)],{'pdfQuality':quality},job)
    output=PdfReader(result['artifact'])
    assert len(output.pages)==1 and 'Compresso test' in output.pages[0].extract_text()
    assert src.read_bytes()==before
    assert result['outputBytes']<=len(before)


def test_mixed_batch_and_duplicate_basenames(tmp_path, job):
    one=tmp_path/'one';two=tmp_path/'two';one.mkdir();two.mkdir()
    image(one/'same.png');image(two/'same.png',mode='RGBA');image(two/'photo.jpg')
    result=compress([str(one/'same.png'),str(two/'same.png'),str(two/'photo.jpg')],{},job)
    with zipfile.ZipFile(result['artifact']) as archive:
        assert archive.namelist()==['same.png','same (2).png','photo.jpg']


def test_zip_keeps_folders_and_applies_tiff_options(tmp_path, job):
    png=tmp_path/'pic.png';image(png)
    tiff=tmp_path/'scan.tif';multipage(tiff)
    src=tmp_path/'bundle.zip'
    with zipfile.ZipFile(src,'w') as archive:
        archive.write(png,'first/pic.png');archive.write(png,'second/pic.png')
        archive.write(tiff,'pages/scan.tif');archive.writestr('skip.txt','unsupported')
    result=compress([str(src)],{'tiffMode':'jpg'},job)
    assert result['skipped']==1
    with zipfile.ZipFile(result['artifact']) as archive:
        assert set(archive.namelist())=={'first/pic.png','second/pic.png','pages/scan-page-001.jpg','pages/scan-page-002.jpg'}


@pytest.mark.parametrize('name',['../outside.png','/absolute.png','C:/drive.png','folder/../../outside.png'])
def test_zip_traversal_rejected(tmp_path, job, name):
    src=tmp_path/'unsafe.zip'
    with zipfile.ZipFile(src,'w') as archive:archive.writestr(name,b'bad')
    with pytest.raises(ValueError,match='unsafe'):compress([str(src)],{},job)


def test_zip_size_limit(tmp_path, job, monkeypatch):
    monkeypatch.setattr(compressor,'MAX_ZIP_BYTES',4)
    src=tmp_path/'huge.zip'
    with zipfile.ZipFile(src,'w') as archive:archive.writestr('big.png',b'12345')
    with pytest.raises(ValueError,match='safety limit'):compress([str(src)],{},job)


def test_unsupported_and_corrupt_files_fail_clearly(tmp_path, job):
    src=tmp_path/'file.txt';src.write_text('x')
    with pytest.raises(ValueError,match='Supported'):compress([str(src)],{},job)
    src=tmp_path/'corrupt.jpg';src.write_bytes(b'broken')
    with pytest.raises(OSError):compress([str(src)],{},job)


def test_cancellation_preserves_source(tmp_path, job):
    src=tmp_path/'original.png';image(src);before=src.read_bytes()
    job.cancelled.set()
    with pytest.raises(Cancelled):compress([str(src)],{},job)
    assert src.read_bytes()==before
