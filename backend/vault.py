"""Version Vault v1: content-defined chunk deltas in a documented ZIP container.

Shared SHA-256 chunks eliminate unchanged regions across versions, including
regions shifted by insertions. Each version can be restored independently.
"""
from pathlib import Path
import hashlib
import json
import zipfile
import zlib
from common import checked_file, fingerprint
from compressor import unique_name

FORMAT = 'compresso-vault'
SCHEMA = 1
MAX_VERSIONS = 200
MAX_TOTAL = 20 * 1024**3
MAX_ENTRIES = 400000
MIN_CHUNK, MAX_CHUNK, MASK = 8192, 131072, (1 << 15) - 1
GEAR = [int.from_bytes(hashlib.sha256(bytes([i])).digest()[:8], 'little') for i in range(256)]


def chunks(reader, job):
    chunk = bytearray()
    rolling = 0
    while block := reader.read(1024 * 1024):
        job.check()
        for byte in block:
            chunk.append(byte)
            rolling = ((rolling << 1) + GEAR[byte]) & 0xffffffffffffffff
            length = len(chunk)
            if length >= MAX_CHUNK or (length >= MIN_CHUNK and rolling & MASK == 0):
                yield bytes(chunk)
                chunk.clear()
                rolling = 0
    if chunk:
        yield bytes(chunk)


def digest_file(path, job):
    digest = hashlib.sha256()
    with path.open('rb') as reader:
        while block := reader.read(1024 * 1024):
            job.check()
            digest.update(block)
    return digest.hexdigest()


def create(paths, options, job):
    if not 2 <= len(paths) <= MAX_VERSIONS:
        raise ValueError('Choose 2–200 related file versions. The first file starts the timeline.')
    sources = [checked_file(p) for p in paths]
    if len(set(sources)) != len(sources):
        raise ValueError('Choose each file only once.')
    snapshots = {str(p): fingerprint(p) for p in sources}
    total = sum(s[2] for s in snapshots.values())
    if total > MAX_TOTAL:
        raise ValueError('This vault exceeds the 20 GiB uncompressed limit.')
    staging = job.directory / 'chunks'
    staging.mkdir()
    artifact = job.directory / 'versions.cvault'
    versions, stored = [], {}
    reference_count = 0
    used_names = set()
    with zipfile.ZipFile(artifact, 'w', zipfile.ZIP_STORED, allowZip64=True) as archive:
        for index, src in enumerate(sources):
            job.progress(f'Finding shared regions · {src.name}', index, len(sources))
            whole = job.directory / 'full.z'
            pending, refs, unique_bytes, reused_bytes = {}, [], 0, 0
            digest, compressor = hashlib.sha256(), zlib.compressobj(6)
            with src.open('rb') as reader, whole.open('wb') as full:
                for chunk in chunks(reader, job):
                    job.check()
                    digest.update(chunk)
                    full.write(compressor.compress(chunk))
                    key = hashlib.sha256(chunk).hexdigest()
                    refs.append({'hash': key, 'size': len(chunk)})
                    reference_count += 1
                    if reference_count > 200000:
                        raise ValueError('This vault needs too many chunk references. Split it into smaller vaults.')
                    if key in stored or key in pending:
                        reused_bytes += len(chunk)
                    else:
                        compressed = zlib.compress(chunk, 6)
                        dest = staging / key
                        dest.write_bytes(compressed)
                        pending[key] = {'path': dest, 'size': len(chunk), 'packed': len(compressed)}
                        unique_bytes += len(compressed)
                full.write(compressor.flush())
            if fingerprint(src) != snapshots[str(src)]:
                raise ValueError(f'{src.name} changed during packing. Try again.')
            # Include references + approximate ZIP headers in the choice; never force a bad delta.
            delta_cost = unique_bytes + len(pending) * 180 + len(json.dumps(refs))
            full_cost = whole.stat().st_size + 180
            chunked = index == 0 or delta_cost < full_cost
            entry = {'id': index, 'name': unique_name(src.name, used_names),
                     'size': snapshots[str(src)][2], 'sha256': digest.hexdigest(),
                     'mode': 'chunks' if chunked else 'full', 'reusedBytes': reused_bytes if chunked else 0}
            if chunked:
                entry['chunks'] = refs
                entry['storedBytes'] = unique_bytes
                for key, value in pending.items():
                    job.check()
                    archive.write(value['path'], f'objects/{key}')
                    stored[key] = value['size']
            else:
                entry['object'] = f'full/{index:04}.z'
                entry['storedBytes'] = whole.stat().st_size
                archive.write(whole, entry['object'])
            for value in pending.values():
                value['path'].unlink(missing_ok=True)
            whole.unlink(missing_ok=True)
            versions.append(entry)
        manifest = {'format': FORMAT, 'schema': SCHEMA, 'codec': 'zlib',
                    'chunker': {'method': 'gear64-v1', 'min': MIN_CHUNK, 'max': MAX_CHUNK, 'mask': MASK},
                    'versions': versions}
        archive.writestr('manifest.json', json.dumps(manifest, separators=(',', ':')))
    for src in sources:
        if fingerprint(src) != snapshots[str(src)]:
            raise ValueError(f'{src.name} changed while packing. Please retry.')
    # Verify every reconstructed version, using one chunk buffer and a streaming digest.
    job.progress('Verifying every version', 0, len(versions))
    with zipfile.ZipFile(artifact) as archive:
        manifest = read_manifest(archive)
        for index, version in enumerate(manifest['versions']):
            job.progress(f'Verifying {version["name"]}', index, len(versions))
            restore_stream(archive, version, None, job)
    return {'artifact': str(artifact), 'name': 'versions.cvault', 'sources': [str(p) for p in sources],
            'inputBytes': total, 'outputBytes': artifact.stat().st_size, 'versions': versions,
            'verified': True, 'sharedBytes': sum(v['reusedBytes'] for v in versions)}


def read_manifest(archive):
    infos = archive.infolist()
    names = [i.filename for i in infos]
    if len(infos) > MAX_ENTRIES or len(set(names)) != len(names):
        raise ValueError('Vault has too many or duplicate entries.')
    if 'manifest.json' not in names:
        raise ValueError('This file is not a Compresso Version Vault.')
    if archive.getinfo('manifest.json').file_size > 32 * 1024**2:
        raise ValueError('Vault manifest is too large.')
    try:
        data = json.loads(archive.read('manifest.json'))
    except (ValueError, UnicodeError) as error:
        raise ValueError('Vault manifest is damaged.') from error
    if not isinstance(data, dict) or data.get('format') != FORMAT or data.get('schema') != SCHEMA or data.get('codec') != 'zlib':
        raise ValueError('Unsupported vault format or version.')
    versions = data.get('versions')
    if not isinstance(versions, list) or not 1 <= len(versions) <= MAX_VERSIONS:
        raise ValueError('Invalid vault version list.')
    total, ref_count = 0, 0
    for index, entry in enumerate(versions):
        if not isinstance(entry, dict) or type(entry.get('id')) is not int or entry['id'] != index:
            raise ValueError('Invalid version identity.')
        name = entry.get('name')
        if not isinstance(name, str) or not name or name in {'.', '..'} or len(name) > 255 or any(c in name for c in '/\\:\0'):
            raise ValueError('Vault contains an unsafe filename.')
        size = entry.get('size')
        if type(size) is not int or not 0 <= size <= MAX_TOTAL or not is_hash(entry.get('sha256')):
            raise ValueError('Invalid version size or digest.')
        total += size
        if total > MAX_TOTAL:
            raise ValueError('Vault expands beyond 20 GiB.')
        if entry.get('mode') == 'chunks':
            refs = entry.get('chunks')
            if not isinstance(refs, list):
                raise ValueError('Invalid chunk list.')
            ref_count += len(refs)
            if ref_count > 1000000:
                raise ValueError('Too many chunk references.')
            length = 0
            for ref in refs:
                if not isinstance(ref, dict) or not is_hash(ref.get('hash')) or type(ref.get('size')) is not int or not 1 <= ref['size'] <= MAX_CHUNK:
                    raise ValueError('Invalid chunk reference.')
                member = f'objects/{ref["hash"]}'
                if member not in archive.NameToInfo or archive.getinfo(member).file_size > MAX_CHUNK + 1024:
                    raise ValueError('Missing or oversized vault chunk.')
                length += ref['size']
            if length != size:
                raise ValueError('Version chunk sizes do not match its length.')
        elif entry.get('mode') == 'full':
            member = f'full/{index:04}.z'
            if entry.get('object') != member or member not in archive.NameToInfo or archive.getinfo(member).file_size > size + size // 100 + 65536:
                raise ValueError('Invalid full-file object.')
        else:
            raise ValueError('Unknown vault storage mode.')
    return data


def is_hash(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def inflated(archive, name, expected, job):
    decoder = zlib.decompressobj()
    count = 0
    with archive.open(name) as reader:
        while packed := reader.read(65536):
            job.check()
            while packed:
                block = decoder.decompress(packed, min(1024 * 1024, expected - count + 1))
                packed = decoder.unconsumed_tail
                count += len(block)
                if count > expected or decoder.unused_data:
                    raise ValueError('Vault object expands beyond its declared size.')
                if block:
                    yield block
    if not decoder.eof or count != expected:
        raise ValueError('Vault object is damaged or truncated.')


def restore_stream(archive, entry, writer, job):
    digest, total = hashlib.sha256(), 0
    if entry['mode'] == 'chunks':
        for ref in entry['chunks']:
            job.check()
            chunk = b''.join(inflated(archive, f'objects/{ref["hash"]}', ref['size'], job))
            if hashlib.sha256(chunk).hexdigest() != ref['hash']:
                raise ValueError('Vault chunk failed its SHA-256 check.')
            total += len(chunk)
            digest.update(chunk)
            if writer:
                writer.write(chunk)
    else:
        for block in inflated(archive, entry['object'], entry['size'], job):
            job.check()
            total += len(block)
            digest.update(block)
            if writer:
                writer.write(block)
    if total != entry['size'] or digest.hexdigest() != entry['sha256']:
        raise ValueError(f'{entry["name"]} failed its SHA-256 check. Nothing should be saved.')


def inspect(paths, options, job):
    src = checked_file(paths[0])
    before = fingerprint(src)
    with zipfile.ZipFile(src) as archive:
        manifest = read_manifest(archive)
    if fingerprint(src) != before:
        raise ValueError('Vault changed while opening. Try again.')
    return {'name': src.name, 'path': str(src), 'versions': manifest['versions'],
            'inputBytes': sum(v['size'] for v in manifest['versions']), 'outputBytes': before[2],
            'verified': False, 'identity': [str(n) for n in before]}


def restore(paths, options, job):
    src = checked_file(paths[0])
    before = fingerprint(src)
    if options.get('identity') and [str(n) for n in before] != [str(n) for n in options['identity']]:
        raise ValueError('The vault changed after opening. Open it again before restoring.')
    version_id = options.get('version', 'all')
    if version_id != 'all' and type(version_id) is not int:
        raise ValueError('Choose a version to restore.')
    outputs, used = [], set()
    with zipfile.ZipFile(src) as archive:
        manifest = read_manifest(archive)
        if version_id != 'all' and not 0 <= version_id < len(manifest['versions']):
            raise ValueError('Version does not exist in this vault.')
        versions = manifest['versions'] if version_id == 'all' else [manifest['versions'][version_id]]
        for index, version in enumerate(versions):
            job.progress(f'Restoring and verifying {version["name"]}', index, len(versions))
            output = job.directory / f'restored-{index}'
            with output.open('wb') as writer:
                restore_stream(archive, version, writer, job)
            outputs.append((output, unique_name(version['name'], used)))
    if fingerprint(src) != before:
        raise ValueError('Vault changed during restoration. Try again.')
    if len(outputs) == 1:
        artifact, name = outputs[0]
    else:
        artifact, name = job.directory / 'restored-versions.zip', 'restored-versions.zip'
        with zipfile.ZipFile(artifact, 'w', zipfile.ZIP_STORED, allowZip64=True) as archive:
            for output, name_in_zip in outputs:
                with output.open('rb') as reader, archive.open(name_in_zip, 'w', force_zip64=True) as writer:
                    while block := reader.read(1024 * 1024):
                        job.check()
                        writer.write(block)
    return {'artifact': str(artifact), 'name': name, 'sources': [str(src)], 'verified': True,
            'outputCount': len(outputs), 'outputBytes': artifact.stat().st_size}
