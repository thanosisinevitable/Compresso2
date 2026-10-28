import pytest
from common import Cancelled
from entropy import analyze


@pytest.mark.parametrize('data,expected', [
    (b'\x00' * 10000, 0), (b'AB' * 10000, 1),
    (bytes(range(256)) * 100, 8), (b'', None), (b'Z', 0),
])
def test_known_distributions(tmp_path, job, data, expected):
    file = tmp_path / 'data.bin'; file.write_bytes(data)
    result = analyze(file, job)
    if expected is None:
        assert result['entropy'] is None and result['redundancy'] is None
    else:
        assert result['entropy'] == pytest.approx(expected)
        assert result['redundancy'] == pytest.approx((1 - expected / 8) * 100)
    assert sum(result['frequencies']) == len(data)
    assert sum(c['size'] for c in result['chunks']) == len(data)
    assert len(result['chunks']) <= 256


def test_heatmap_covers_all_bytes_and_distinguishes_sections(tmp_path, job):
    file = tmp_path / 'sections.bin'
    file.write_bytes(b'\0' * 16384 + bytes(range(256)) * 64 + b'END')
    result = analyze(file, job)
    assert result['chunks'][0]['entropy'] == 0
    assert result['chunks'][16]['entropy'] == 8
    assert result['chunks'][-1]['size'] == 3
    cursor = 0
    for chunk in result['chunks']:
        assert chunk['offset'] == cursor
        cursor += chunk['size']
    assert cursor == file.stat().st_size


def test_large_file_is_chunked_and_cancelable(tmp_path, job):
    file = tmp_path / 'large.bin'
    with file.open('wb') as stream:
        for _ in range(6): stream.write(bytes(range(256)) * 4096)
    result = analyze(file, job)
    assert len(result['chunks']) == 256
    assert result['entropy'] == 8
    job.cancelled.set()
    with pytest.raises(Cancelled): analyze(file, job)


def test_symlink_is_rejected(tmp_path, job):
    target = tmp_path / 'target'; target.write_bytes(b'abc')
    link = tmp_path / 'link'; link.symlink_to(target)
    with pytest.raises(ValueError): analyze(link, job)


def test_changed_file_is_not_reported_as_valid(tmp_path, job, monkeypatch):
    import entropy
    file=tmp_path/'changing';file.write_bytes(b'initial')
    original=entropy.fingerprint
    calls=0
    def changed(path):
        nonlocal calls
        calls+=1
        identity=original(path)
        if calls>1:identity[3]+=1
        return identity
    monkeypatch.setattr(entropy,'fingerprint',changed)
    with pytest.raises(ValueError,match='changed'):analyze(file,job)
