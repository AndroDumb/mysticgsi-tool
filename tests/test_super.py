import hashlib
import os
import struct

import pytest

from tools.extractor.formats import super as lp_super

SECTOR = 512
MAX_SIZE = 65536
SLOTS = 2
METADATA_START = 4096 + 2 * 4096
DATA_START = METADATA_START + 2 * SLOTS * MAX_SIZE


def _metadata(partitions):
    """partitions: [(name, [(num_sectors, type, target_sector)])]"""
    extents, entries = b"", b""
    for name, part_extents in partitions:
        first = len(extents) // 24
        for num_sectors, target_type, target in part_extents:
            extents += struct.pack(
                '<QIQI', num_sectors, target_type, target, 0)
        entries += struct.pack('<36sIIII', name.encode(), 0, first,
                               len(part_extents), 0)

    tables = entries + extents
    header = bytearray(struct.pack(
        '<IHHI32sI32s12I', lp_super.LP_METADATA_HEADER_MAGIC, 10, 0, 128,
        bytes(32), len(tables), hashlib.sha256(tables).digest(),
        0, len(partitions), 52,
        len(entries), len(extents) // 24, 24,
        0, 0, 48,
        0, 0, 64))
    header[12:44] = hashlib.sha256(header).digest()
    return bytes(header) + tables


def _build_super(path, partitions, payloads, corrupt_primary=None):
    geometry = struct.pack('<II32sIII', lp_super.LP_METADATA_GEOMETRY_MAGIC,
                           52, bytes(32), MAX_SIZE, SLOTS, 4096)
    metadata = _metadata(partitions)
    with open(path, 'wb') as f:
        for offset in (4096, 8192):
            f.seek(offset)
            f.write(geometry)
        for slot in range(2 * SLOTS):
            f.seek(METADATA_START + slot * MAX_SIZE)
            f.write(metadata)
        if corrupt_primary is not None:
            f.seek(METADATA_START + corrupt_primary)
            f.write(b'garbage')
        for sector, data in payloads:
            f.seek(sector * SECTOR)
            f.write(data)
        f.truncate(max(f.tell(), DATA_START + 64 * 1024))


def _unpack(tmp_path, **kwargs):
    system = os.urandom(8 * SECTOR)
    vendor_tail = os.urandom(2 * SECTOR)
    first = DATA_START // SECTOR
    image = tmp_path / "super.img"
    _build_super(image, [
        ("system_a", [(8, lp_super.LP_TARGET_TYPE_LINEAR, first)]),
        ("system_b", [(8, lp_super.LP_TARGET_TYPE_LINEAR, first + 16)]),
        ("vendor_a", [(4, lp_super.LP_TARGET_TYPE_ZERO, 0),
                      (2, lp_super.LP_TARGET_TYPE_LINEAR, first + 32)]),
        ("odm_a", []),
    ], [(first, system), (first + 32, vendor_tail)], **kwargs)

    out = tmp_path / "out"
    extracted = lp_super.unpack_super(str(image), str(out))
    names = sorted(os.path.basename(p) for p in extracted)
    return out, names, system, vendor_tail


def test_unpack_follows_extents_and_skips_redundant_slot(tmp_path):
    out, names, system, vendor_tail = _unpack(tmp_path)

    assert names == ["system_a.img", "vendor_a.img"]
    assert (out / "system_a.img").read_bytes() == system
    assert (out / "vendor_a.img").read_bytes() == \
        bytes(4 * SECTOR) + vendor_tail


# 60 lands in the header, 200 in the partition/extent tables.
@pytest.mark.parametrize("corrupt_at", [60, 200])
def test_corrupt_primary_metadata_falls_back_to_next_slot(tmp_path,
                                                          corrupt_at):
    out, names, system, _ = _unpack(tmp_path, corrupt_primary=corrupt_at)

    assert names == ["system_a.img", "vendor_a.img"]
    assert (out / "system_a.img").read_bytes() == system
