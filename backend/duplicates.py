"""Size-filtered SHA-256 and anchor-based pHash grouping, without symlink traversal."""
from collections import defaultdict
import hashlib
import os
from pathlib import Path
import warnings
from PIL import Image, ImageOps
import imagehash
from common import fingerprint

IMAGE_TYPES = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.webp', '.bmp', '.gif'}
MAX_FILES = 200000


def sha256(path, job=None):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            if job:
                job.check()
            digest.update(block)
    return digest.hexdigest()


class HashTree:
    """BK-tree over 64-bit Hamming distance; only group anchors are indexed."""
    def __init__(self):
        self.root = None

    def add(self, value, index):
        node = [value, index, {}]
        if self.root is None:
            self.root = node
            return
        current = self.root
        while True:
            distance = (value ^ current[0]).bit_count()
            if distance not in current[2]:
                current[2][distance] = node
                return
            current = current[2][distance]

    def nearest(self, value, threshold):
        pending = [self.root] if self.root else []
        best = None
        while pending:
            current = pending.pop()
            distance = (value ^ current[0]).bit_count()
            if distance <= threshold and (best is None or (distance, current[1]) < best):
                best = (distance, current[1])
            pending.extend(node for edge, node in current[2].items() if distance - threshold <= edge <= distance + threshold)
        return best


def scan(folder, options, job):
    root = Path(folder).absolute()
    if root.resolve() != root or root.is_symlink() or not root.is_dir():
        raise ValueError('Choose a readable folder, not a symbolic link.')
    threshold = options.get('threshold', 8)
    visual = options.get('visual', True)
    if type(threshold) is not int or not 0 <= threshold <= 16 or type(visual) is not bool:
        raise ValueError('Similarity distance must be an integer from 0 to 16.')
    records, notices = [], []
    counts = {'filesScanned': 0, 'skipped': 0, 'symlinksSkipped': 0, 'hardlinksSkipped': 0, 'errorCount': 0}

    def warn(message):
        counts['errorCount'] += 1
        if len(notices) < 100:
            notices.append(message)

    stack = [root]
    while stack:
        job.check()
        directory = stack.pop()
        try:
            if directory.is_symlink() or directory.resolve() != directory:
                counts['symlinksSkipped'] += 1
                continue
            with os.scandir(directory) as entries:
                for entry in entries:
                    job.check()
                    try:
                        if entry.is_symlink():
                            counts['symlinksSkipped'] += 1
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            counts['skipped'] += 1
                            continue
                        counts['filesScanned'] += 1
                        info = entry.stat(follow_symlinks=False)
                        if info.st_nlink > 1:
                            counts['hardlinksSkipped'] += 1
                            continue
                        path = Path(entry.path)
                        record = {'path': str(path), 'name': path.name, 'size': info.st_size,
                                  'image': path.suffix.lower() in IMAGE_TYPES,
                                  'fingerprint': fingerprint(path)}
                        records.append(record)
                        if len(records) >= MAX_FILES:
                            raise ValueError('Folder exceeds 200,000 files. Choose a smaller subfolder.')
                        if len(records) % 100 == 0:
                            job.progress('Discovering files', counts['filesScanned'])
                    except (OSError, ValueError) as error:
                        if isinstance(error, ValueError) and '200,000' in str(error):
                            raise
                        warn(f'{entry.name}: {error}')
        except OSError as error:
            warn(f'{directory}: {error}')
    records.sort(key=lambda f: f['path'])
    by_size = defaultdict(list)
    for record in records:
        by_size[record['size']].append(record)
    candidates = [record for group in by_size.values() if len(group) > 1 for record in group]
    by_digest = defaultdict(list)
    invalid = set()
    for index, record in enumerate(candidates):
        job.progress(f'Comparing contents · {record["name"]}', index, len(candidates))
        try:
            path = Path(record['path'])
            if fingerprint(path) != record['fingerprint']:
                raise ValueError('File changed during scan')
            digest = sha256(path, job)
            if fingerprint(path) != record['fingerprint']:
                raise ValueError('File changed during scan')
            record['sha256'] = digest
            by_digest[(record['size'], digest)].append(record)
        except (OSError, ValueError) as error:
            invalid.add(record['path'])
            warn(f'{record["name"]}: {error}')
    groups = []
    for (_, digest), files in by_digest.items():
        if len(files) > 1:
            groups.append({'id': f'exact-{len(groups)}', 'kind': 'exact', 'sha256': digest,
                           'files': files, 'potentialBytes': sum(f['size'] for f in files[1:])})
    exact_representatives = {f['path'] for g in groups for f in g['files'][1:]}
    if visual:
        images = [r for r in records if r['image'] and r['path'] not in invalid and r['path'] not in exact_representatives]
        tree, visual_groups = HashTree(), []
        for index, record in enumerate(images):
            job.progress(f'Comparing images · {record["name"]}', index, len(images))
            try:
                path = Path(record['path'])
                if fingerprint(path) != record['fingerprint']:
                    raise ValueError('File changed during scan')
                with warnings.catch_warnings():
                    warnings.simplefilter('error', Image.DecompressionBombWarning)
                    with Image.open(path) as image:
                        image.draft('RGB', (512, 512))
                        oriented = ImageOps.exif_transpose(image)
                        value = int(str(imagehash.phash(oriented, hash_size=8)), 16)
                if fingerprint(path) != record['fingerprint']:
                    raise ValueError('File changed during scan')
                match = tree.nearest(value, threshold)
                visual_record = {**record, 'phash': f'{value:016x}'}
                if match is None:
                    tree.add(value, len(visual_groups))
                    visual_groups.append([{**visual_record, 'distance': 0, 'similarity': 100.0}])
                else:
                    distance, group_index = match
                    visual_groups[group_index].append({**visual_record, 'distance': distance,
                                                       'similarity': round(100 * (1 - distance / 64), 2)})
            except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
                warn(f'{record["name"]}: image similarity skipped ({error})')
        for files in visual_groups:
            if len(files) > 1:
                groups.append({'id': f'visual-{len(groups)}', 'kind': 'similar', 'files': files,
                               'potentialBytes': sum(f['size'] for f in files[1:])})
    # Remove files changed since earlier stages so stale matches are not presented as reliable.
    stable = []
    for group in groups:
        try:
            for record in group['files']:
                if fingerprint(Path(record['path'])) != record['fingerprint']:
                    raise ValueError('File changed during scan')
            stable.append(group)
        except (OSError, ValueError) as error:
            warn(f'One group was omitted: {error}')
    groups = stable
    job.progress('Scan complete', counts['filesScanned'], counts['filesScanned'])
    return {'folder': str(root), 'groups': groups, 'threshold': threshold,
            **counts, 'warnings': notices,
            'exactGroups': sum(g['kind'] == 'exact' for g in groups),
            'similarGroups': sum(g['kind'] == 'similar' for g in groups),
            'recoverableBytes': sum(g['potentialBytes'] for g in groups if g['kind'] == 'exact')}


def validate_cleanup(result, selected):
    paths = set(selected)
    if not paths:
        raise ValueError('Select at least one duplicate.')
    records = {f['path']: f for g in result['groups'] for f in g['files']}
    if not paths <= records.keys():
        raise ValueError('Selection contains a file outside these scan results.')
    touched = [g for g in result['groups'] if any(f['path'] in paths for f in g['files'])]
    keepers = defaultdict(list)
    for group in touched:
        retained = [f for f in group['files'] if f['path'] not in paths]
        if not retained:
            raise ValueError('Keep at least one file in every group, including overlapping groups.')
        for record in group['files']:
            path = Path(record['path'])
            if fingerprint(path) != record['fingerprint']:
                raise ValueError(f'{record["name"]} changed or moved since the scan. Scan again.')
            if group['kind'] == 'exact' and sha256(path) != group['sha256']:
                raise ValueError('File contents changed. Scan again before removing anything.')
            if fingerprint(path) != record['fingerprint']:
                raise ValueError('File changed during verification. Scan again.')
        keeper = retained[0]
        for record in group['files']:
            if record['path'] in paths:
                keepers[record['path']].append({'path': keeper['path'], 'identity': [str(n) for n in keeper['fingerprint']]})
    return {'hasSimilar': any(g['kind'] == 'similar' for g in touched),
            'files': [{'path': p, 'identity': [str(n) for n in records[p]['fingerprint']], 'keepers': keepers[p]} for p in sorted(paths)]}
