import os
from pathlib import Path
import pytest
from PIL import Image, ImageDraw
import duplicates
from common import Cancelled
from duplicates import HashTree, scan, validate_cleanup


def fixture_folder(tmp_path):
    folder = tmp_path / 'scan'; folder.mkdir()
    return folder


def test_sha256_sizes_renaming_and_nonmatches(tmp_path, job, monkeypatch):
    folder = fixture_folder(tmp_path)
    (folder/'original').write_bytes(b'abcdef')
    (folder/'renamed').write_bytes(b'abcdef')
    (folder/'same-size-different').write_bytes(b'fedcba')
    (folder/'unique-size').write_bytes(b'12345')
    hashed = []
    actual = duplicates.sha256
    def tracking(path, job=None):
        hashed.append(path.name)
        return actual(path, job)
    monkeypatch.setattr(duplicates, 'sha256', tracking)
    result = scan(folder, {'visual': False}, job)
    assert result['filesScanned'] == 4 and result['exactGroups'] == 1
    assert result['recoverableBytes'] == 6
    assert {f['name'] for f in result['groups'][0]['files']} == {'original','renamed'}
    assert 'unique-size' not in hashed


def test_resize_and_exact_groups_are_distinct(tmp_path, job):
    folder = fixture_folder(tmp_path)
    image = Image.new('RGB', (640,480), '#cfa34e')
    draw = ImageDraw.Draw(image)
    draw.rectangle((30,70,200,280), fill='#2d51a9')
    draw.ellipse((220,180,530,460), fill='#91d29e')
    draw.line((0,0,639,479), fill='white', width=8)
    image.save(folder/'original.png')
    image.resize((320,240)).save(folder/'resized.jpg', quality=92)
    (folder/'renamed.png').write_bytes((folder/'original.png').read_bytes())
    result = scan(folder, {'threshold':8}, job)
    assert result['exactGroups'] == 1 and result['similarGroups'] == 1
    similar = next(g for g in result['groups'] if g['kind']=='similar')
    assert len(similar['files']) == 2
    assert all(f['distance'] <= 8 and f['similarity'] >= 87.5 for f in similar['files'])
    assert result['recoverableBytes'] == (folder/'original.png').stat().st_size


def test_threshold_and_anchor_distance():
    tree = HashTree(); tree.add(0,0);tree.add(255,1)
    assert tree.nearest(3,1) is None
    assert tree.nearest(3,2) == (2,0)
    assert tree.nearest(255,0) == (0,1)


def test_symlinks_and_hardlinks_are_excluded(tmp_path, job):
    folder = fixture_folder(tmp_path)
    (folder/'a').write_bytes(b'data');(folder/'b').write_bytes(b'data')
    (folder/'cycle').symlink_to(folder, target_is_directory=True)
    (folder/'sym').symlink_to(folder/'a')
    os.link(folder/'a',folder/'hard')
    result = scan(folder, {'visual':False}, job)
    assert result['symlinksSkipped'] == 2
    assert result['hardlinksSkipped'] == 2
    assert result['exactGroups'] == 0


def test_unreadable_subfolder_is_reported(tmp_path, job, monkeypatch):
    folder = fixture_folder(tmp_path);(folder/'unreadable').mkdir()
    (folder/'a').write_bytes(b'x');(folder/'b').write_bytes(b'x')
    actual = os.scandir
    def guarded(path):
        if Path(path).name == 'unreadable': raise PermissionError('Access denied')
        return actual(path)
    monkeypatch.setattr(duplicates.os,'scandir',guarded)
    result = scan(folder, {'visual':False}, job)
    assert result['exactGroups'] == 1 and result['errorCount'] == 1


def test_cleanup_requires_retained_unchanged_copy(tmp_path, job):
    folder = fixture_folder(tmp_path)
    a=folder/'a';b=folder/'b';a.write_bytes(b'hello');b.write_bytes(b'hello')
    result = scan(folder, {'visual':False}, job)
    plan = validate_cleanup(result,[str(b)])
    assert plan['files'][0]['keepers'][0]['path'] == str(a)
    assert isinstance(plan['files'][0]['identity'][3],str)
    with pytest.raises(ValueError,match='Keep at least one'): validate_cleanup(result,[str(a),str(b)])
    with pytest.raises(ValueError,match='outside'): validate_cleanup(result,[str(folder/'unknown')])
    a.write_bytes(b'other')
    with pytest.raises(ValueError,match='changed'): validate_cleanup(result,[str(b)])


def test_corrupt_image_does_not_abort_scan(tmp_path, job):
    folder = fixture_folder(tmp_path)
    (folder/'bad.png').write_bytes(b'not an image')
    result = scan(folder, {}, job)
    assert result['filesScanned']==1 and result['errorCount']==1


def test_scan_can_be_cancelled(tmp_path, job):
    folder=fixture_folder(tmp_path);job.cancelled.set()
    with pytest.raises(Cancelled):scan(folder,{},job)


def test_slightly_edited_image_is_a_review_candidate(tmp_path,job):
    from PIL import ImageEnhance
    folder=fixture_folder(tmp_path)
    photo=Image.new('RGB',(400,300),'#997145')
    draw=ImageDraw.Draw(photo);draw.rectangle((20,90,240,270),fill='#367b82');draw.ellipse((150,30,350,210),fill='#ddd3b2')
    photo.save(folder/'original.png')
    edited=ImageEnhance.Brightness(photo).enhance(1.08)
    ImageDraw.Draw(edited).rectangle((380,280,388,288),fill='white')
    edited.save(folder/'edited.jpg',quality=85)
    result=scan(folder,{'threshold':8},job)
    assert result['exactGroups']==0 and result['similarGroups']==1


def test_link_swap_in_directory_queue_is_not_followed(tmp_path,job,monkeypatch):
    folder=fixture_folder(tmp_path);nested=folder/'nested';nested.mkdir()
    outside=tmp_path/'outside';outside.mkdir();(outside/'secret').write_bytes(b'x')
    actual=duplicates.os.scandir
    class SwapAfterListing:
        def __enter__(self):
            self.stream=actual(folder)
            return self.stream
        def __exit__(self,*args):
            self.stream.close();nested.rmdir();nested.symlink_to(outside,target_is_directory=True)
    def guarded(path):
        if Path(path)==folder:return SwapAfterListing()
        if Path(path)==nested:raise AssertionError('A replaced directory symlink was followed')
        return actual(path)
    monkeypatch.setattr(duplicates.os,'scandir',guarded)
    result=scan(folder,{'visual':False},job)
    assert result['filesScanned']==0 and result['symlinksSkipped']==1
