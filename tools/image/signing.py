"""AVB signing for raw GSI system images."""

import os
import sys

import fsops

AVB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "avb")
AVBTOOL = os.path.join(AVB_DIR, "avbtool.py")
TEST_KEY = os.path.join(AVB_DIR, "testkey_rsa2048.pem")


def sign_system_image(image, logger=None):
    """Signs and verifies a staged image; returns the avbtool exit code."""
    log = logger or print
    log("Signing system image with AOSP AVB test key")
    command = [sys.executable, AVBTOOL]
    rc = fsops.run(command + [
        "add_hashtree_footer", "--image", image,
        "--partition_name", "system", "--partition_size", "0",
        "--algorithm", "SHA256_RSA2048", "--key", TEST_KEY,
        "--hash_algorithm", "sha256", "--do_not_generate_fec",
    ])
    if rc == 0:
        rc = fsops.run(command + [
            "verify_image", "--image", image, "--key", TEST_KEY,
        ])
    if rc != 0:
        log(f"AVB signing or verification failed ({rc})")
    return rc
