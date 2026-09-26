# AOSP AVB tools

`avbtool.py`, `testkey_rsa2048.pem` and `LICENSE` are unmodified files from
[platform/external/avb, android-16.0.0_r1](https://android.googlesource.com/platform/external/avb/+/refs/tags/android-16.0.0_r1/).
The key is AOSP's publicly available test private key, not a secret.

Signing follows the system image algorithm and key in AOSP's
[BoardConfigGsiCommon.mk](https://android.googlesource.com/platform/build/+/refs/tags/android-16.0.0_r1/target/board/BoardConfigGsiCommon.mk).
FEC is omitted to avoid requiring the Android `fec` host tool.
