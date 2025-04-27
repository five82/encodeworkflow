#!/bin/bash

# build_ffmpeg_static.sh
# Builds a static FFmpeg binary on macOS (Homebrew) or Debian (Linuxbrew)
# Includes: libsvtav1, libopus

# --- Configuration ---
INSTALL_PREFIX="$HOME/ffmpeg_static"
BUILD_DIR="/tmp/ffmpeg_build_temp"
FFMPEG_REPO="https://git.ffmpeg.org/ffmpeg.git"
FFMPEG_BRANCH="master"
SVT_AV1_REPO="https://gitlab.com/AOMediaCodec/SVT-AV1.git" # svt-av1
#SVT_AV1_REPO="https://github.com/BlueSwordM/svt-av1-psyex.git" # svt-av1-psyex
SVT_AV1_BRANCH="master"
OPUS_REPO="https://gitlab.xiph.org/xiph/opus.git"
OPUS_BRANCH="main"

# --- Helper Functions ---
_log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        _log "Error: Required command '$1' not found. Please install it."
        exit 1
    fi
}

# --- Clean Previous Build Directory ---
if [ -d "$BUILD_DIR" ]; then
    _log "Removing previous build directory: $BUILD_DIR"
    rm -rf "$BUILD_DIR"
fi
if [ -d "$INSTALL_PREFIX" ]; then
    _log "Removing previous install directory: $INSTALL_PREFIX"
    rm -rf "$INSTALL_PREFIX"
fi

# --- Strict Mode & Error Handling ---
set -euo pipefail
trap 'echo "Error on line $LINENO"; exit 1' ERR

# --- OS Detection & Setup ---
OS_NAME=$(uname -s)
BREW_CMD=""
CPU_COUNT=""

_log "Detected OS: $OS_NAME"

if [[ "$OS_NAME" == "Darwin" ]]; then
    _log "Setting up for macOS (Homebrew)"
    BREW_CMD="brew"
    CPU_COUNT=$(sysctl -n hw.ncpu)
elif [[ "$OS_NAME" == "Linux" ]]; then
    _log "Setting up for Linux (Linuxbrew)"
    # Check for Debian specifically if needed, but Linuxbrew path is the main goal
    if [[ -f /etc/debian_version ]]; then
        _log "Debian detected."
    fi
    # Standard Linuxbrew path or fallback to Homebrew path if installed differently
    if [[ -x "/home/linuxbrew/.linuxbrew/bin/brew" ]]; then
         BREW_CMD="/home/linuxbrew/.linuxbrew/bin/brew"
    elif command -v brew &> /dev/null; then
         BREW_CMD="brew" # Assume brew is in PATH if not in default Linuxbrew location
    fi
    CPU_COUNT=$(nproc)
else
    _log "Error: Unsupported operating system '$OS_NAME'."
    exit 1
fi

if [[ -z "$BREW_CMD" ]]; then
     _log "Error: brew command not found. Please install Homebrew (macOS) or Linuxbrew (Debian)."
     _log "macOS: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
     _log "Debian/Linux: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
     exit 1
fi

_log "Using brew command: $BREW_CMD"
_log "Using CPU cores: $CPU_COUNT"

# --- Update Brew ---
_log "Updating brew..."
"$BREW_CMD" update || _log "Warning: Brew update failed, continuing..."

# --- Install Dependencies ---
_log "Installing dependencies..."
DEPS=(
    cmake
    nasm
    pkg-config
    git # For cloning ffmpeg source
    wget # For opus model download
    autoconf # For opus autogen.sh
    automake # For opus autogen.sh
    libtool # For opus autogen.sh
    # svt-av1 and opus will be built from source
)

for dep in "${DEPS[@]}"; do
    if "$BREW_CMD" list "$dep" &> /dev/null; then
        _log "$dep is already installed."
    else
        _log "Installing $dep..."
        "$BREW_CMD" install "$dep"
    fi
done

_log "Dependencies installed."

# --- Environment Configuration ---
_log "Configuring build environment..."
BREW_PREFIX=$("$BREW_CMD" --prefix)
# Prepend our custom install prefix paths FIRST so they are preferred
export PKG_CONFIG_PATH="${INSTALL_PREFIX}/lib/pkgconfig:${INSTALL_PREFIX}/lib64/pkgconfig:${PKG_CONFIG_PATH:-}"
export CFLAGS="-I${INSTALL_PREFIX}/include -O3 ${CFLAGS:-}" # Add -O3 for optimization
export CXXFLAGS="-I${INSTALL_PREFIX}/include -O3 ${CXXFLAGS:-}" # Add -O3 for optimization
export LDFLAGS="-L${INSTALL_PREFIX}/lib -L${INSTALL_PREFIX}/lib64 ${LDFLAGS:-}"

# Append brew paths as fallback
BREW_PREFIX=$("$BREW_CMD" --prefix)
export PKG_CONFIG_PATH="${PKG_CONFIG_PATH}:${BREW_PREFIX}/lib/pkgconfig"
# Ensure -O3 is present even if CFLAGS/CXXFLAGS were initially empty
export CFLAGS="${CFLAGS:- -O3} -I${BREW_PREFIX}/include"
export CXXFLAGS="${CXXFLAGS:- -O3} -I${BREW_PREFIX}/include"
export LDFLAGS="${LDFLAGS} -L${BREW_PREFIX}/lib"

_log "PKG_CONFIG_PATH=$PKG_CONFIG_PATH"
_log "CFLAGS=$CFLAGS"
_log "CXXFLAGS=$CXXFLAGS"
_log "LDFLAGS=$LDFLAGS"

# --- Prepare Directories ---
_log "Creating directories..."
mkdir -p "$BUILD_DIR"
mkdir -p "$INSTALL_PREFIX"
rm -rf "$BUILD_DIR/ffmpeg" # Clean previous ffmpeg source attempt
rm -rf "$BUILD_DIR/SVT-AV1" # Clean previous svt-av1 source attempt
rm -rf "$BUILD_DIR/opus" # Clean previous opus source attempt

# --- Build SVT-AV1 from Source ---
_log "Cloning SVT-AV1 source (branch: $SVT_AV1_BRANCH)..."
cd "$BUILD_DIR"
git clone --depth 1 --branch "$SVT_AV1_BRANCH" "$SVT_AV1_REPO" SVT-AV1
cd SVT-AV1

_log "Configuring SVT-AV1..."
mkdir -p Build # Use standard CMake build directory convention
cd Build
cmake .. \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    -DBUILD_SHARED_LIBS=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_APPS=OFF # We only need the library

_log "Building SVT-AV1 (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Installing SVT-AV1..."
make install
_log "SVT-AV1 installation complete."

# --- Build opus from Source ---
_log "Cloning opus source (branch: $OPUS_BRANCH)..."
cd "$BUILD_DIR"
git clone --depth 1 --branch "$OPUS_BRANCH" "$OPUS_REPO" opus
cd opus

_log "Configuring opus..."
./autogen.sh # Opus requires autogen before configure
./configure \
    --prefix="$INSTALL_PREFIX" \
    --enable-static \
    --disable-shared \
    --disable-doc \
    --disable-extra-programs

_log "Building opus (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Installing opus..."
make install
_log "opus installation complete."


# --- Download FFmpeg ---
_log "Downloading FFmpeg source (branch: $FFMPEG_BRANCH)..."
cd "$BUILD_DIR" # Go back to build dir
git clone --depth 1 --branch "$FFMPEG_BRANCH" "$FFMPEG_REPO" ffmpeg
cd ffmpeg

# --- Configure FFmpeg ---
_log "Configuring FFmpeg..."

./configure \
    --prefix="$INSTALL_PREFIX" \
    --pkg-config-flags="--static" \
    --enable-static \
    --disable-shared \
    --enable-gpl \
    --enable-libsvtav1 \
    --enable-libopus \
    --disable-xlib \
    --disable-libxcb \
    --disable-vaapi \
    --disable-vdpau \
    --extra-cflags="$CFLAGS" \
    --extra-ldflags="$LDFLAGS"

_log "FFmpeg configuration complete."

# --- Build and Install ---
_log "Building FFmpeg (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Build complete. Installing FFmpeg..."
make install
_log "Installation complete."

# --- Validate Static Linking ---
_log "Validating static linking..."
BINARIES=(ffmpeg ffprobe) # ffplay is likely not built due to --disable-xlib/--disable-libxcb
VALIDATION_FAILED=0

for binary in "${BINARIES[@]}"; do
    binary_path="$INSTALL_PREFIX/bin/$binary"
    if [[ ! -f "$binary_path" ]]; then
        _log "Error: Binary $binary_path not found for validation."
        VALIDATION_FAILED=1
        continue
    fi

    _log "Checking $binary..."
    if [[ "$OS_NAME" == "Darwin" ]]; then
        linked_libs=$(otool -L "$binary_path")
        dynamic_brew_libs=()
        # Check for brew-installed dynamic libs we wanted static
        # Check for dynamic libs we built ourselves (should NOT be listed dynamically)
        if echo "$linked_libs" | grep -q "$INSTALL_PREFIX/lib/libopus"; then dynamic_brew_libs+=("opus (dynamic)"); fi
        if echo "$linked_libs" | grep -q "$INSTALL_PREFIX/lib/libSvtAv1Enc"; then dynamic_brew_libs+=("SvtAv1Enc (dynamic)"); fi


        if [ ${#dynamic_brew_libs[@]} -gt 0 ]; then
            _log "Error: $binary appears dynamically linked against: ${dynamic_brew_libs[*]}"
            echo "$linked_libs" # Print full output for debugging
            VALIDATION_FAILED=1
        else
            _log "$binary linkage appears static (no unexpected dynamic libs found)."
        fi
    elif [[ "$OS_NAME" == "Linux" ]]; then
        ldd_output=$(ldd "$binary_path" 2>&1) || true # Capture output even if ldd fails

        # Failure condition 1: Dynamically linked against our locally built libs in INSTALL_PREFIX
        if echo "$ldd_output" | grep -q -E "$INSTALL_PREFIX/lib/libopus.so|$INSTALL_PREFIX/lib/libSvtAv1Enc.so"; then
            _log "Error: $binary appears dynamically linked against locally built libs:"
            echo "$ldd_output" | grep --color=never "$INSTALL_PREFIX/lib/" | grep -E --color=never 'libopus.so|libSvtAv1Enc.so'
            VALIDATION_FAILED=1
        # Success condition: No dynamic links to our local builds found
        else
            _log "$binary linkage appears correct (no unexpected dynamic libs found)."
            # Optional: Log the actual system dependencies found
            # log "ldd output (system libs expected):"
            # echo "$ldd_output" | grep -v "$INSTALL_PREFIX/lib/" # Exclude our local path if any somehow slipped through grep -q
        fi
    fi
done

if [[ "$VALIDATION_FAILED" -eq 1 ]]; then
    _log "Error: Static linking validation failed for one or more binaries."
    exit 1
else
    _log "Static linking validation passed."
fi

# --- Cleanup ---
_log "Cleaning up build directory..."
# cd "$HOME" # Go back home before removing build dir
# rm -rf "$BUILD_DIR"
_log "Build directory $BUILD_DIR kept for inspection. Remove manually if desired."

# --- Final Message ---
_log "--------------------------------------------------"
_log "Static FFmpeg build successful!"
_log "The static binaries (ffmpeg, ffprobe) are located at: $INSTALL_PREFIX/bin/"
_log "--------------------------------------------------"

exit 0
