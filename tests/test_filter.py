import zipfile

from tools.extractor import extract_firmware, postprocess

TARGETS = {"system", "vendor", "product"}


def test_member_filter_keeps_only_what_the_pipeline_uses():
    kept = {
        "system.img", "system_a.img", "vendor-sign.img", "product.img.ext4",
        "super.img", "super_1.img", "system.img_sparsechunk.3",
        "system.new.dat.br", "system.transfer.list", "AP_G998B.tar.md5",
        "system_X-FLASH-ALL-C93B.sin", "UPDATE.APP", "fw.kdz",
    }
    dropped = {"modem.img", "boot.img", "NON-HLOS.bin", "xbl.elf",
               "vendor_boot.img", "system_other.img"}

    assert {n for n in kept | dropped
            if postprocess.is_wanted(n, TARGETS)} == kept


def test_qfil_archives_are_not_filtered(tmp_path):
    fw = tmp_path / "fw.zip"
    with zipfile.ZipFile(fw, "w") as zf:
        zf.writestr("rawprogram0.xml", """<data>
          <program SECTOR_SIZE_IN_BYTES="512" label="system"
                   filename="piece_1.img" start_sector="0"/></data>""")
        zf.writestr("piece_1.img", b"\x01" * 4096)

    rc = extract_firmware(str(fw), str(tmp_path / "out"),
                          target_partitions=["system"], logger=print)

    assert rc == 0
    assert (tmp_path / "out" / "system.img").read_bytes() == b"\x01" * 4096
