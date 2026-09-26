import os
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from make import RomPorter
from tools.image import signing


@pytest.mark.skipif(not shutil.which("openssl"), reason="needs OpenSSL")
def test_signed_image_has_valid_footer_and_detects_corruption(tmp_path):
    image = tmp_path / "system.img"
    payload = bytes(range(256)) * 4096
    image.write_bytes(payload)

    assert signing.sign_system_image(str(image)) == 0
    with image.open("rb") as stream:
        assert stream.read(len(payload)) == payload
        stream.seek(-64, os.SEEK_END)
        magic, major, minor, original, offset, size = struct.unpack(
            "!4sIIQQQ28x", stream.read(64))
        assert (magic, major, minor, original) == (
            b"AVBf", 1, 0, len(payload))
        assert original < offset < image.stat().st_size - 64
        assert size > 0
    verify = [sys.executable, signing.AVBTOOL, "verify_image",
              "--image", str(image), "--key", signing.TEST_KEY]
    assert subprocess.run(verify, capture_output=True).returncode == 0

    with image.open("r+b") as stream:
        stream.seek(4096)
        stream.write(b"corrupted")
    assert subprocess.run(verify, capture_output=True).returncode != 0


@pytest.mark.skipif(not shutil.which("openssl"), reason="needs OpenSSL")
def test_rebuild_publishes_and_compresses_signed_image(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    system = tmp_path / "tmp/test/images/system"
    system.mkdir(parents=True)
    out = tmp_path / "out/test"
    out.mkdir(parents=True)
    (out / "rebuilt.zip").write_bytes(b"stale archive")
    (out / "output.txt").write_text("Raw Image Size: old\n")
    payload = bytes(range(256)) * 4096

    def build_image(**kwargs):
        Path(kwargs["output_image"]).write_bytes(payload)
        return 0

    monkeypatch.setattr("tools.build_system_image", build_image)
    porter = RomPorter("test")
    size = porter.rebuild("rebuilt")
    image = out / "rebuilt.img"
    assert size == image.stat().st_size > len(payload)
    assert not (out / "rebuilt.zip").exists()
    assert "old" not in (out / "output.txt").read_text()
    assert porter.compress_output() == 0
    with zipfile.ZipFile(out / "rebuilt.zip") as archive:
        assert archive.namelist() == ["system.img"]
        assert archive.read("system.img") == image.read_bytes()
    (out / "system.img").symlink_to(image.name)
    result = subprocess.run([
        sys.executable, signing.AVBTOOL, "verify_image",
        "--image", str(out / "system.img"), "--key", signing.TEST_KEY,
    ], capture_output=True)
    assert result.returncode == 0


@pytest.mark.parametrize("failed_step", [
    "add_hashtree_footer", "verify_image",
])
def test_signing_failure_preserves_published_image(
        tmp_path, monkeypatch, failed_step):
    monkeypatch.chdir(tmp_path)
    system = tmp_path / "system"
    system.mkdir()
    out = tmp_path / "out/test"
    out.mkdir(parents=True)
    destination = out / "previous.img"
    destination.write_bytes(b"previous signed image")
    porter = RomPorter("test")
    porter.partition_dirs = {"system": str(system)}
    porter.images_dir = str(tmp_path)

    def build_image(**kwargs):
        Path(kwargs["output_image"]).write_bytes(b"new filesystem")
        return 0

    def run_signing(command):
        image = Path(command[command.index("--image") + 1])
        image.write_bytes(b"partial signature")
        return 1 if command[2] == failed_step else 0

    monkeypatch.setattr("tools.build_system_image", build_image)
    monkeypatch.setattr(signing.fsops, "run", run_signing)
    assert porter._write_image("previous") is None
    assert destination.read_bytes() == b"previous signed image"
    assert list(out.iterdir()) == [destination]
