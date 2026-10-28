# Compresso Version Vault — schema 1

A `.cvault` file is a standard ZIP container with application-defined content. It preserves file bytes and basenames; it is not an encrypted archive and does not preserve filesystem permissions, Finder tags or directory structures. Restore through Compresso, since ordinary ZIP extraction yields the internal objects rather than the original versions.

## Container

- `manifest.json`: UTF-8 JSON containing `format: "compresso-vault"`, `schema: 1`, `codec: "zlib"`, chunker parameters and an ordered `versions` list.
- `objects/<sha256>`: a zlib stream that expands to a shared content chunk whose SHA-256 matches its name.
- `full/0001.z`, etc.: a zlib stream containing a complete version when sharing chunks would cost more.

ZIP members use ZIP_STORED because their payloads are already zlib-compressed. ZIP CRCs add transport checks; SHA-256 checks establish that the restored bytes match the recorded version. Hashes are not signatures or authentication against a malicious archive author.

## Chunk boundaries

The chunker reads bounded 1 MiB blocks and carries state across read boundaries. A content chunk is at least 8,192 bytes and at most 131,072 bytes. Once the minimum is reached, a boundary is created when the lower 15 bits of the rolling hash are zero, or when the maximum is reached.

The rolling state starts at zero for each chunk and updates per byte:

```python
gear[byte] = int.from_bytes(sha256(bytes([byte])).digest()[:8], "little")
h = ((h << 1) + gear[byte]) & 0xffffffffffffffff
```

A trailing chunk may be shorter than the minimum. Content-defined boundaries let matching regions resynchronize after insertions; they do not guarantee a particular saving. Each chunk is identified with its full SHA-256 digest, independently of the rolling boundary hash.

## Version entries

All entries have an ordinal integer `id`, safe basename `name`, byte `size`, full-file `sha256`, `mode`, `storedBytes` and `reusedBytes`.

For `mode: "chunks"`, `chunks` is an ordered list of `{ "hash": "<64 lowercase hex digits>", "size": <bytes> }`. Restore concatenates these chunks and checks both chunk and full-file hashes. Chunk objects may be shared with earlier chunk-stored versions or earlier occurrences in the same file.

For `mode: "full"`, `object` is exactly `full/<id padded to four digits>.z`. Restore streams this object and checks its full-file hash. Full-file fallback objects are not additionally indexed as shared chunks, keeping the format and random-access restoration simple.

The first version uses chunk storage. Later versions compare the cost of new compressed chunks and references against full-file compression. Shared-byte counts are logical uncompressed bytes; new-content counts exclude container and manifest overhead. The timeline is the user-selected input order, not inferred file history or modification dates.

## Integrity and limits

Creation reconstructs and verifies every version before exposing the save action. Opening validates the index, object references, names and declared sizes. It does not read every payload; restoring performs the complete hash checks for the selected version(s).

Limits are 200 versions, 20 GiB of total restored bytes, 200,000 generated chunk references, a 32 MiB manifest and 400,000 ZIP entries. Import additionally limits chunk reference counts, chunk sizes and full-object lengths. Decompression stops if an object exceeds its declared byte size, and truncated or trailing compressed data is rejected. Import never extracts member paths to the filesystem. Native saving rejects overwriting selected source files or hard links to them.

This format uses content-defined chunk deltas implemented in Python; it is not VCDIFF/xdelta and does not require an additional executable. Future incompatible changes must use a new schema version.
