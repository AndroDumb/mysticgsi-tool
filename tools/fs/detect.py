"""
In-memory binary magic detector for filesystem images.
"""


def detect_filesystem(file_path: str) -> str:
    """
    Detects whether an image file contains an ext4, erofs, or f2fs filesystem.
    Returns: 'ext4', 'erofs', 'f2fs', or 'unknown'
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(2048)
    except OSError:
        return 'unknown'

    if len(header) < 1084:
        return 'unknown'

    # EROFS: superblock at 1024, magic 0xE0F5E1E2
    if header[1024:1028] == b'\xe2\xe1\xf5\xe0':
        return 'erofs'

    # F2FS: superblock at 1024, magic 0xF2F52010
    if header[1024:1028] == b'\x10\x20\xf5\xf2':
        return 'f2fs'

    # ext2/3/4: superblock at 1024, s_magic 0xEF53 at +0x38
    if header[1080:1082] == b'\x53\xef':
        return 'ext4'

    return 'unknown'
