import os
import struct

from tools.extractor import postprocess
from tools.extractor.formats import sparse

BLK = 4096


def _sparse_image(total_blocks, chunks):
    """chunks: [(chunk_type, blocks, payload)] covering total_blocks."""
    body = b""
    for chunk_type, blocks, payload in chunks:
        body += struct.pack('<2H2I', chunk_type, 0, blocks,
                            12 + len(payload)) + payload
    header = struct.pack('<I4H4I', sparse.SPARSE_HEADER_MAGIC, 1, 0, 28, 12,
                         BLK, total_blocks, len(chunks), 0)
    return header + body


def _chunk_covering(index, total_blocks, payload):
    """A sparsechunk that writes one block at `index` and skips the rest."""
    chunks = []
    if index:
        chunks.append((sparse.CHUNK_TYPE_DONT_CARE, index, b""))
    chunks.append((sparse.CHUNK_TYPE_RAW, 1, payload))
    if index + 1 < total_blocks:
        chunks.append(
            (sparse.CHUNK_TYPE_DONT_CARE, total_blocks - index - 1, b""))
    return _sparse_image(total_blocks, chunks)


def test_sparsechunks_merge_in_numeric_order_per_partition(tmp_path):
    total = 12
    blocks = [os.urandom(BLK) for _ in range(11)]
    for i, block in enumerate(blocks):
        (tmp_path / f"system.img_sparsechunk.{i}").write_bytes(
            _chunk_covering(i, total, block))
    fill = _sparse_image(2, [(sparse.CHUNK_TYPE_FILL, 2, b"\xab\xcd\xef\x01")])
    (tmp_path / "system_ext.img_sparsechunk.0").write_bytes(fill)

    postprocess._merge_sparse_chunks(str(tmp_path), None)

    assert (tmp_path / "system.img").read_bytes() == \
        b"".join(blocks) + bytes(BLK)
    assert (tmp_path / "system_ext.img").read_bytes() == \
        b"\xab\xcd\xef\x01" * (2 * BLK // 4)
    assert sorted(os.listdir(tmp_path)) == ["system.img", "system_ext.img"]
