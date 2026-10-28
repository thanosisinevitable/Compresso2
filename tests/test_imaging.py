from pathlib import Path
import zipfile
import numpy as np
import pytest
from PIL import Image
from common import Cancelled, fingerprint
from imaging import compare, target_lock


def photo(path, size=(600,400)):
    rng=np.random.default_rng(42)
    data=rng.integers(0,256,(*size[::-1],3),dtype=np.uint8)
    Image.fromarray(data).save(path)


def test_target_verifies_exact_budget_and_dimensions(tmp_path,job):
    src=tmp_path/'photo.png';photo(src)
    before=src.read_bytes()
    result=target_lock([str(src)],{'targetBytes':45000},job)
    row=result['rows'][0]
    assert row['met'] and row['outputBytes']<=45000
    with Image.open(result['artifact']) as image:
        assert image.size==(600,400) and image.format=='JPEG'
    assert not row['resized'] and row['quality'] is not None
    assert src.read_bytes()==before
    assert row['attempts'] and len(row['attempts'])<=14


def test_infeasible_target_produces_no_savable_file(tmp_path,job):
    src=tmp_path/'photo.png';photo(src)
    result=target_lock([str(src)],{'targetBytes':1024},job)
    assert result['successCount']==0 and result['artifact'] is None
    assert result['rows'][0]['smallestAttemptBytes']>1024
    assert not result['rows'][0]['resized']


def test_explicit_resize_can_make_target_feasible(tmp_path,job):
    src=tmp_path/'photo.png';photo(src)
    result=target_lock([str(src)],{'targetBytes':2500,'allowResize':True},job)
    assert result['rows'][0]['resized'] and result['rows'][0]['met']
    assert Path(result['artifact']).stat().st_size<=2500
    assert result['rows'][0]['width']<600


def test_existing_jpeg_under_budget_is_unchanged(tmp_path,job):
    src=tmp_path/'original.jpg';photo(src,(40,40))
    result=target_lock([str(src)],{'targetBytes':100000},job)
    assert Path(result['artifact']).read_bytes()==src.read_bytes()
    assert result['rows'][0]['quality'] is None


def test_batch_collision_names_and_all_outputs_fit(tmp_path,job):
    a=tmp_path/'one';b=tmp_path/'two';a.mkdir();b.mkdir()
    for folder in [a,b]:photo(folder/'same.png',(100,100))
    result=target_lock([str(a/'same.png'),str(b/'same.png')],{'targetBytes':9000},job)
    with zipfile.ZipFile(result['artifact']) as archive:
        assert set(archive.namelist())=={'same.jpg','same (2).jpg'}
        assert all(info.file_size<=9000 for info in archive.infolist())
    assert len(result['lensPairs'])==2


def test_multipage_is_not_silently_flattened(tmp_path,job):
    src=tmp_path/'pages.tif'
    Image.new('RGB',(10,10),'red').save(src,save_all=True,append_images=[Image.new('RGB',(10,10),'blue')])
    with pytest.raises(ValueError,match='single-frame'):target_lock([str(src)],{'targetBytes':10000},job)


@pytest.mark.parametrize('value',[True,0,1023,100*1024**2+1,'500'])
def test_invalid_target_is_rejected(tmp_path,job,value):
    src=tmp_path/'photo.png';photo(src,(20,20))
    with pytest.raises(ValueError):target_lock([str(src)],{'targetBytes':value},job)


def test_lens_identical_lossless_image_has_perfect_score(tmp_path,job):
    src=tmp_path/'same.png';photo(src,(50,40))
    result=compare([str(src),str(src)],{},job)
    assert result['ssim']==pytest.approx(1) and result['identicalPreview']
    assert result['meanAbsoluteError']==0 and result['psnr'] is None
    with Image.open(result['assets']['heatmap']) as heat:
        assert not np.asarray(heat).any()


def test_lens_detects_loss_and_saves_all_preview_layers(tmp_path,job):
    src=tmp_path/'original.png';photo(src,(80,70))
    compressed=tmp_path/'compressed.jpg'
    with Image.open(src) as image:image.save(compressed,quality=5)
    result=compare([str(src),str(compressed)],{'gain':16},job)
    assert result['ssim']<1 and result['meanAbsoluteError']>0 and result['psnr']>0
    assert set(result['assets'])=={'original','compressed','difference','heatmap'}
    for asset in result['assets'].values():assert Path(asset).is_file()


def test_lens_calls_out_resize_and_tiny_image_metric(tmp_path,job):
    src=tmp_path/'large.png';photo(src,(40,30))
    out=tmp_path/'tiny.png'
    with Image.open(src) as image:image.resize((4,3)).save(out)
    result=compare([str(src),str(out)],{},job)
    assert result['resized'] and result['previewWidth']==4
    assert result['originalWidth']==40 and result['outputWidth']==4


def test_lens_refuses_changed_source(tmp_path,job):
    src=tmp_path/'photo.png';photo(src,(20,20))
    identity=fingerprint(src)
    Image.new('RGB',(20,20),'red').save(src)
    with pytest.raises(ValueError,match='changed'):compare([str(src),str(src)],{'identity':identity},job)


def test_target_cancel_preserves_original(tmp_path,job):
    src=tmp_path/'photo.png';photo(src,(20,20));before=src.read_bytes()
    job.cancelled.set()
    with pytest.raises(Cancelled):target_lock([str(src)],{'targetBytes':2000},job)
    assert src.read_bytes()==before


def test_transparent_png_is_explicitly_composited_on_white(tmp_path,job):
    src=tmp_path/'alpha.png';Image.new('RGBA',(24,24),(255,0,0,0)).save(src)
    result=target_lock([str(src)],{'targetBytes':5000},job)
    with Image.open(result['artifact']) as image:
        assert min(image.convert('RGB').getpixel((10,10)))>245


def test_orientation_is_applied_before_target_dimensions(tmp_path,job):
    src=tmp_path/'portrait.jpg'
    im=Image.new('RGB',(120,80),'red');exif=Image.Exif();exif[274]=6
    im.save(src,exif=exif,quality=100)
    # Force a re-encoding instead of the already-fitting original shortcut.
    result=target_lock([str(src)],{'targetBytes':1024},job)
    row=result['rows'][0]
    assert (row['originalWidth'],row['originalHeight'])==(80,120)


def test_browser_roundtrip_identity_uses_precision_safe_strings(tmp_path,job):
    src=tmp_path/'photo.png';photo(src,(40,30))
    result=target_lock([str(src)],{'targetBytes':5000},job)
    pair=result['lensPairs'][0]
    assert all(isinstance(n,str) for n in pair['identity'])
    compared=compare([pair['source'],pair['output']],{'identity':pair['identity']},job)
    assert compared['ssim'] is not None
