import os
import struct

import pytest

from tools.fs.ext4 import Ext4Filesystem
from tools.host import configure_environment, find_tool
from tools.image import build_system_image

configure_environment()
pytestmark = pytest.mark.skipif(
    not (find_tool("mke2fs") and find_tool("e2fsdroid")),
    reason="needs mke2fs and e2fsdroid")


def _fs_config_entry(prefix, mode, uid, gid):
    raw = prefix.encode() + b"\0"
    raw += b"\0" * (-(16 + len(raw)) % 8)
    return struct.pack('<HHHHQ', 16 + len(raw), mode, uid, gid, 0) + raw


def test_image_gets_stock_owners_and_modes(tmp_path):
    src = tmp_path / "src"
    for path in ("system/bin/sh", "system/product/bin/tool"):
        os.makedirs(src / os.path.dirname(path), exist_ok=True)
        (src / path).write_bytes(b"x")
        os.chmod(src / path, 0o644)
    os.makedirs(src / "system/product/etc")
    (src / "system/product/etc/fs_config_files").write_bytes(
        _fs_config_entry("product/bin/tool", 0o750, 1000, 1001))

    image = tmp_path / "system.img"
    assert build_system_image(str(src), str(image), 16 << 20,
                              staging_dir=str(tmp_path / "st"),
                              logger=lambda m: None) == 0

    with Ext4Filesystem(str(image)) as fs:
        sh = fs.stat("system/bin/sh")
        tool = fs.stat("system/product/bin/tool")
    assert (sh.mode & 0o7777, sh.uid, sh.gid) == (0o755, 0, 2000)
    assert (tool.mode & 0o7777, tool.uid, tool.gid) == (0o750, 1000, 1001)
