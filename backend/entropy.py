"""Empirical, zero-order byte entropy. Every byte is counted; no sampling."""
from collections import Counter
import math
import mimetypes
from common import checked_file, fingerprint


def shannon(counts, total):
    if total == 0:
        return None
    return max(0.0, -sum((count / total) * math.log2(count / total) for count in counts if count))


def explanation(entropy, size):
    if not size:
        return 'This file is empty. It has no byte distribution, so entropy and redundancy are undefined.'
    if entropy >= 7.5:
        text = 'This file exhibits high byte entropy, suggesting relatively low statistical redundancy at the byte level. Already-compressed or encrypted files often behave this way, making further lossless compression difficult.'
    elif entropy >= 5:
        text = 'This file has a moderately varied byte distribution. Some byte values are more common than others, suggesting statistical redundancy that an entropy coder may exploit.'
    else:
        text = 'This file has low byte entropy. Its byte distribution is concentrated in relatively few values, indicating substantial byte-level statistical redundancy.'
    text += ' Byte entropy ignores the order of bytes: repeated sequences can still compress well even when their byte entropy is high. This is not a prediction of a compression ratio or proof of encryption.'
    if size < 4096:
        text += ' This is a small file; limited sample size can make the measured entropy appear low.'
    return text


def analyze(value, job):
    path = checked_file(value)
    before = fingerprint(path)
    size = before[2]
    chunk_size = max(1024, math.ceil(size / 256))
    frequencies = [0] * 256
    chunks, offset = [], 0
    with path.open('rb') as reader:
        while offset < size:
            job.check()
            target = min(chunk_size, size - offset)
            local = Counter()
            read = 0
            while read < target:
                job.check()
                block = reader.read(min(1024 * 1024, target - read))
                if not block:
                    raise ValueError('File changed during analysis. Please retry.')
                local.update(block)
                read += len(block)
            for byte, count in local.items():
                frequencies[byte] += count
            chunks.append({'index': len(chunks), 'offset': offset, 'size': read,
                           'entropy': shannon(local.values(), read)})
            offset += read
            job.progress('Reading every byte', offset, size)
        if reader.read(1):
            raise ValueError('File grew during analysis. Please retry.')
    if fingerprint(path) != before:
        raise ValueError('File changed during analysis. Please retry.')
    entropy = shannon(frequencies, size)
    job.progress('Analysis complete', size, size)
    return {'path': str(path), 'name': path.name, 'size': size,
            'type': mimetypes.guess_type(path.name)[0] or 'application/octet-stream',
            'extension': path.suffix.lower() or 'No extension',
            'entropy': entropy, 'redundancy': (1 - entropy / 8) * 100 if entropy is not None else None,
            'frequencies': frequencies, 'chunks': chunks, 'chunkSize': chunk_size,
            'explanation': explanation(entropy, size)}
