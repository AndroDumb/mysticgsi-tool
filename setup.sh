#!/usr/bin/env bash
# Installs MysticGSI's dependencies on macOS, Debian/Ubuntu, Arch and NixOS.
#
#   ./setup.sh          runtime dependencies
#   ./setup.sh --dev    plus pytest and flake8
#
# Safe to re-run: package managers skip what is installed, and the native
# image tools are only rebuilt when missing.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"
REQUIREMENTS="$ROOT/requirements.txt"
MIN_PYTHON="3.10"

log() { printf '\033[1m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

for arg in "$@"; do
    case "$arg" in
        --dev) REQUIREMENTS="$ROOT/requirements-dev.txt" ;;
        -h|--help) sed -n '2,8s/^# \{0,1\}//p' "$0"; exit 0 ;;
        *) die "unknown option: $arg" ;;
    esac
done

as_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    elif command -v sudo >/dev/null; then
        sudo "$@"
    else
        die "need root for: $*"
    fi
}

make_venv() {
    local python="$1"
    "$python" -c "import sys; sys.exit(sys.version_info < (${MIN_PYTHON/./, }))" \
        || die "Python >= $MIN_PYTHON required, found $("$python" --version)"
    log "Creating $VENV with $("$python" --version)"
    "$python" -m venv "$VENV"
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet -r "$REQUIREMENTS"
}

native_tools_present() {
    "$VENV/bin/python" - <<'EOF'
import sys
sys.path.insert(0, ".")
from tools.host import check_environment
try:
    check_environment()
except RuntimeError:
    sys.exit(1)
EOF
}

build_native_tools() {
    if native_tools_present; then
        return
    fi
    log "Building mke2fs.android and e2fsdroid from source"
    "$VENV/bin/python" "$ROOT/tools/build_android_tools.py"
}

# Arch only packages apktool in the AUR and Debian's is years old, so fetch
# the upstream release jar instead.
install_apktool() {
    if command -v apktool >/dev/null; then
        return
    fi
    local bin="$HOME/.local/bin"
    log "Installing apktool into $bin"
    local url
    url="$(curl -fsSL https://api.github.com/repos/iBotPeaches/Apktool/releases/latest \
        | "$VENV/bin/python" -c '
import json, sys
assets = json.load(sys.stdin)["assets"]
print(next(a["browser_download_url"] for a in assets
           if a["name"].startswith("apktool_") and a["name"].endswith(".jar")))
')"
    mkdir -p "$bin"
    curl -fL --progress-bar -o "$bin/apktool.jar" "$url"
    printf '#!/bin/sh\nexec java -jar "%s/apktool.jar" "$@"\n' "$bin" \
        > "$bin/apktool"
    chmod +x "$bin/apktool"
    case ":$PATH:" in
        *":$bin:"*) ;;
        *) warn "$bin is not on PATH; add it to your shell profile" \
               "so builds can find apktool" ;;
    esac
}

setup_macos() {
    command -v brew >/dev/null || die "install Homebrew first: https://brew.sh"
    xcode-select -p >/dev/null 2>&1 \
        || die "install the Command Line Tools first: xcode-select --install"

    log "Installing Homebrew packages"
    brew install python@3.13 cmake ninja pkgconf erofs-utils brotli lz4 \
        pcre2 libusb zstd protobuf aria2 apktool gpatch

    make_venv "$(brew --prefix python@3.13)/bin/python3.13"
    build_native_tools
}

setup_debian() {
    # The second half builds mke2fs.android and e2fsdroid, which Debian
    # doesn't package.
    local packages="python3 python3-venv python3-pip erofs-utils aria2 patch
        default-jre-headless curl ca-certificates
        build-essential cmake ninja-build pkg-config perl golang-go
        libgtest-dev libusb-1.0-0-dev libpcre2-dev libprotobuf-dev
        protobuf-compiler libbrotli-dev liblz4-dev libzstd-dev"

    log "Installing apt packages"
    as_root apt-get update
    # shellcheck disable=SC2086
    as_root apt-get install -y $packages

    make_venv python3
    install_apktool
    build_native_tools
}

setup_arch() {
    log "Installing pacman packages"
    # -Syu: Arch doesn't support installing against a stale package database.
    as_root pacman -Syu --needed python python-pip erofs-utils aria2 patch \
        jre-openjdk-headless android-tools curl

    make_venv python
    install_apktool
    native_tools_present \
        || die "android-tools did not provide mke2fs.android and e2fsdroid"
}

setup_nixos() {
    command -v nix >/dev/null || die "nix not found"
    log "Building the nix dev shell"
    nix --extra-experimental-features 'nix-command flakes' \
        develop "$ROOT" --command python3 -c 'import tools'
    log "Done. Enter the environment with: nix develop"
    log "Then run builds with: python3 cli.py build <name> <firmware>"
}

# fsck.erofs gained --extract in erofs-utils 1.5 (Ubuntu 22.04 ships 1.4).
check_erofs() {
    if ! command -v fsck.erofs >/dev/null \
            || ! fsck.erofs --help 2>&1 | grep -q -- --extract; then
        warn "fsck.erofs with --extract (erofs-utils >= 1.5) not found;" \
            "EROFS partitions can't be unpacked"
    fi
}

detect_linux() {
    [ -r /etc/os-release ] || die "cannot identify this Linux distribution"
    # shellcheck disable=SC1091
    . /etc/os-release
    case " ${ID:-} ${ID_LIKE:-} " in
        *" nixos "*) echo nixos ;;
        *" arch "*) echo arch ;;
        *" debian "*|*" ubuntu "*) echo debian ;;
        *) die "unsupported distribution '${ID:-unknown}'; see README.md" ;;
    esac
}

main() {
    cd "$ROOT"
    case "$(uname -s)" in
        Darwin) setup_macos ;;
        Linux)
            local distro
            distro="$(detect_linux)"
            if [ "$distro" = nixos ]; then
                setup_nixos
                return
            fi
            "setup_$distro"
            ;;
        *) die "unsupported OS: $(uname -s)" ;;
    esac

    log "Checking the environment"
    "$VENV/bin/python" -c 'import tools; tools.check_environment()'
    check_erofs
    log "Done. Build a GSI with: .venv/bin/python cli.py build <name> <firmware>"
}

main
