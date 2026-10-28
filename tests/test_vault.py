import io
import json
from pathlib import Path
import random
import zipfile
import zlib
import pytest
from common import Cancelled
from vault import create, inspect, restore, chunks
from conftest import TestJob as JobFixture


def job_at(root,name):
    path=root/name;path.mkdir();return JobFixture(path)


def inputs(tmp_path):
    rng=random.Random(7)
    base=rng.randbytes(900000)
    files=[tmp_path/'design-1.bin',tmp_path/'design-2.bin',tmp_path/'design-3.bin']
    data=[base,base[:150000]+b'An inserted caption.'+base[150000:],base[:500000]+b'new edit'*30+base[500240:]]
    for path,payload in zip(files,data):path.write_bytes(payload)
    return files,data


def test_vault_shared_regions_and_every_version_restores_exactly(tmp_path,job):
    files,data=inputs(tmp_path)
    packed=create([str(p) for p in files],{},job)
    assert packed['verified'] and packed['outputBytes']<packed['inputBytes']*.7
    assert packed['versions'][1]['reusedBytes']>500000
    for i,payload in enumerate(data):
        restored=restore([packed['artifact']],{'version':i},job_at(tmp_path,f'restore-{i}'))
        assert restored['verified'] and Path(restored['artifact']).read_bytes()==payload
    assert [p.read_bytes() for p in files]==data


def test_open_and_restore_all_preserves_names_and_bytes(tmp_path,job):
    files,data=inputs(tmp_path);packed=create([str(p) for p in files],{},job)
    opened=inspect([packed['artifact']],{},job)
    assert not opened['verified'] and len(opened['versions'])==3
    restored=restore([packed['artifact']],{'version':'all'},job_at(tmp_path,'all'))
    with zipfile.ZipFile(restored['artifact']) as archive:
        assert archive.namelist()==[p.name for p in files]
        assert [archive.read(p.name) for p in files]==data


def test_unrelated_file_uses_full_fallback(tmp_path,job):
    a=tmp_path/'a';b=tmp_path/'b'
    a.write_bytes(random.Random(1).randbytes(300000));b.write_bytes(random.Random(2).randbytes(300000))
    result=create([str(a),str(b)],{},job)
    assert result['versions'][1]['mode']=='full'
    restored=restore([result['artifact']],{'version':1},job_at(tmp_path,'restore'))
    assert Path(restored['artifact']).read_bytes()==b.read_bytes()


def test_identical_and_empty_files(tmp_path,job):
    files=[tmp_path/'a',tmp_path/'b',tmp_path/'c',tmp_path/'d']
    for p,data in zip(files,[b'constant'*100000,b'constant'*100000,b'',b'']):p.write_bytes(data)
    result=create([str(p) for p in files],{},job)
    assert result['versions'][1]['storedBytes']==0
    restored=restore([result['artifact']],{'version':3},job_at(tmp_path,'empty'))
    assert Path(restored['artifact']).read_bytes()==b''


def rewrite(src,dst,mutation):
    with zipfile.ZipFile(src) as archive:
        contents={n:archive.read(n) for n in archive.namelist()}
    mutation(contents)
    with zipfile.ZipFile(dst,'w') as archive:
        for name,data in contents.items():archive.writestr(name,data)


def test_corrupted_chunk_is_rejected_before_save(tmp_path,job):
    files,_=inputs(tmp_path);result=create([str(p) for p in files],{},job)
    damaged=tmp_path/'damaged.cvault'
    def corrupt(contents):
        manifest=json.loads(contents['manifest.json']);ref=manifest['versions'][0]['chunks'][0]
        contents['objects/'+ref['hash']]=zlib.compress(b'x'*ref['size'])
    rewrite(result['artifact'],damaged,corrupt)
    with pytest.raises(ValueError,match='SHA-256'):restore([str(damaged)],{'version':0},job_at(tmp_path,'corrupt'))


@pytest.mark.parametrize('name',['../outside','/absolute','a\\bad','C:drive','\x00bad'])
def test_unsafe_restore_names_are_rejected(tmp_path,job,name):
    files,_=inputs(tmp_path);result=create([str(p) for p in files],{},job)
    damaged=tmp_path/'unsafe.cvault'
    def unsafe(contents):
        manifest=json.loads(contents['manifest.json']);manifest['versions'][0]['name']=name
        contents['manifest.json']=json.dumps(manifest).encode()
    rewrite(result['artifact'],damaged,unsafe)
    with pytest.raises(ValueError,match='unsafe filename'):inspect([str(damaged)],{},job)


def test_object_expansion_limit_is_enforced(tmp_path,job):
    files,_=inputs(tmp_path);result=create([str(p) for p in files],{},job)
    damaged=tmp_path/'bomb.cvault'
    def bomb(contents):
        manifest=json.loads(contents['manifest.json']);ref=manifest['versions'][0]['chunks'][0]
        contents['objects/'+ref['hash']]=zlib.compress(b'x'*(ref['size']+1))
    rewrite(result['artifact'],damaged,bomb)
    with pytest.raises(ValueError,match='beyond'):restore([str(damaged)],{'version':0},job_at(tmp_path,'bomb'))


def test_chunking_is_read_boundary_independent(tmp_path,job):
    data=random.Random(30).randbytes(300000)
    class SmallReads(io.BytesIO):
        def read(self,n=-1):return super().read(min(n,101))
    assert list(chunks(io.BytesIO(data),job))==list(chunks(SmallReads(data),job))


def test_cancellation_and_invalid_restore_index(tmp_path,job):
    files,_=inputs(tmp_path);result=create([str(p) for p in files],{},job)
    with pytest.raises(ValueError):restore([result['artifact']],{'version':500},job_at(tmp_path,'invalid'))
    cancelled=job_at(tmp_path,'cancelled');cancelled.cancelled.set()
    with pytest.raises(Cancelled):restore([result['artifact']],{'version':0},cancelled)


def test_restore_refuses_archive_changed_after_opening(tmp_path,job):
    files,_=inputs(tmp_path);packed=create([str(p) for p in files],{},job)
    opened=inspect([packed['artifact']],{},job)
    assert all(isinstance(n,str) for n in opened['identity'])
    identity=[*opened['identity']];identity[3]=str(int(identity[3])+1)
    with pytest.raises(ValueError,match='changed after opening'):
        restore([packed['artifact']],{'version':0,'identity':identity},job_at(tmp_path,'changed'))
