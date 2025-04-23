#!/bin/bash

# build_ffmpeg_static.sh
# Builds a static FFmpeg binary on macOS (Homebrew) or Debian (Linuxbrew)
# Includes: libsvtav1, libx264, libx265, libopus

# --- Configuration ---
INSTALL_PREFIX="$HOME/ffmpeg_static"
BUILD_DIR="/tmp/ffmpeg_build_temp"
FFMPEG_BRANCH="master" # Build from master branch
SVT_AV1_BRANCH="master" # Build svt-av1 from master branch
X264_BRANCH="stable" # Use stable branch due to master build issues on ARM
X265_BRANCH="master"
OPUS_BRANCH="main" # Opus uses 'main' as its default branch

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
    # svt-av1, x264, x265, opus will be built from source
    # libva will be installed conditionally below for Linux
)

for dep in "${DEPS[@]}"; do
    if "$BREW_CMD" list "$dep" &> /dev/null; then
        _log "$dep is already installed."
    else
        _log "Installing $dep..."
        "$BREW_CMD" install "$dep"
    fi
done

# Install Linux-specific dependencies
if [[ "$OS_NAME" == "Linux" ]]; then
    _log "Installing Linux-specific dependencies (libva)..."
    if "$BREW_CMD" list libva &> /dev/null; then
        _log "libva is already installed."
    else
        _log "Installing libva..."
        "$BREW_CMD" install libva
    fi
fi

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
rm -rf "$BUILD_DIR/x264" # Clean previous x264 source attempt
rm -rf "$BUILD_DIR/x265_git" # Clean previous x265 source attempt
rm -rf "$BUILD_DIR/opus" # Clean previous opus source attempt

# --- Build SVT-AV1 from Source ---
_log "Cloning SVT-AV1 source (branch: $SVT_AV1_BRANCH)..."
cd "$BUILD_DIR"
git clone --depth 1 --branch "$SVT_AV1_BRANCH" https://gitlab.com/AOMediaCodec/SVT-AV1.git SVT-AV1
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


# --- Build x264 from Source ---
_log "Cloning x264 source (branch: $X264_BRANCH)..."
cd "$BUILD_DIR"
git clone --depth 1 --branch "$X264_BRANCH" https://code.videolan.org/videolan/x264.git x264
cd x264

_log "Configuring x264..."
# Note: --enable-pic is important for static libs that will be linked into FFmpeg
./configure \
    --prefix="$INSTALL_PREFIX" \
    --enable-static \
    --disable-shared \
    --enable-pic \
    --disable-cli # We only need the library

_log "Building x264 (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Installing x264..."
make install
_log "x264 installation complete."


# --- Build x265 from Source ---
_log "Cloning x265 source (branch: $X265_BRANCH)..."
cd "$BUILD_DIR"
# Note: The repo name is x265_git, but we clone into 'x265' directory for consistency
git clone --depth 1 --branch "$X265_BRANCH" https://bitbucket.org/multicoreware/x265_git.git x265
cd x265/build/linux # x265 uses build directories

_log "Configuring x265..."
# x265 uses CMake
cmake ../../source \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    -DENABLE_SHARED=OFF \
    -DENABLE_CLI=OFF \
    -DCMAKE_BUILD_TYPE=Release

_log "Building x265 (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Installing x265..."
make install
_log "x265 installation complete."


# --- Build opus from Source ---
_log "Cloning opus source (branch: $OPUS_BRANCH)..."
cd "$BUILD_DIR"
git clone --depth 1 --branch "$OPUS_BRANCH" https://gitlab.xiph.org/xiph/opus.git opus
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
git clone --depth 1 --branch "$FFMPEG_BRANCH" https://git.ffmpeg.org/ffmpeg.git ffmpeg
cd ffmpeg

# --- Configure FFmpeg ---
_log "Configuring FFmpeg..."

# Add platform-specific hardware acceleration flags
FFMPEG_HW_FLAGS=""
if [[ "$OS_NAME" == "Darwin" ]]; then
    _log "Enabling VideoToolbox for macOS hardware acceleration."
    FFMPEG_HW_FLAGS="--enable-videotoolbox"
elif [[ "$OS_NAME" == "Linux" ]]; then
    _log "Enabling VA-API for Linux hardware acceleration."
    FFMPEG_HW_FLAGS="--enable-vaapi"
fi
./configure \
    --prefix="$INSTALL_PREFIX" \
    --pkg-config-flags="--static" \
    --enable-static \
    --disable-shared \
    --enable-gpl \
    --enable-libsvtav1 \
    --enable-libx264 \
    --enable-libx265 \
    --enable-libopus \
    --extra-cflags="$CFLAGS" \
    --extra-ldflags="$LDFLAGS" \
    $FFMPEG_HW_FLAGS

_log "FFmpeg configuration complete."

# --- Build and Install ---
_log "Building FFmpeg (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Build complete. Installing FFmpeg..."
make install
_log "Installation complete."

# --- Validate Static Linking ---
_log "Validating static linking..."
BINARIES=(ffmpeg ffplay ffprobe)
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
        if echo "$linked_libs" | grep -q "$INSTALL_PREFIX/lib/libx264"; then dynamic_brew_libs+=("x264 (dynamic)"); fi
        if echo "$linked_libs" | grep -q "$INSTALL_PREFIX/lib/libx265"; then dynamic_brew_libs+=("x265 (dynamic)"); fi
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
        if echo "$ldd_output" | grep -q -E "$INSTALL_PREFIX/lib/libx264.so|$INSTALL_PREFIX/lib/libx265.so|$INSTALL_PREFIX/lib/libopus.so|$INSTALL_PREFIX/lib/libSvtAv1Enc.so"; then
            _log "Error: $binary appears dynamically linked against locally built libs:"
            echo "$ldd_output" | grep --color=never "$INSTALL_PREFIX/lib/"
            VALIDATION_FAILED=1
        # Failure condition 2: Dynamically linked against libva.so (should be static libva.a)
        elif echo "$ldd_output" | grep -q 'libva.so'; then
            _log "Error: $binary appears dynamically linked against libva.so (should be static):"
            echo "$ldd_output" | grep --color=never 'libva.so'
            VALIDATION_FAILED=1
        # Success condition: No dynamic links to our local builds or libva.so found
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
_log "The static binaries (ffmpeg, ffplay, ffprobe) are located at: $INSTALL_PREFIX/bin/"
if [[ "$OS_NAME" == "Linux" ]]; then
    _log "NOTE: VA-API hardware acceleration enabled, but requires runtime drivers (e.g., intel-media-va-driver or mesa-va-drivers) installed via your system package manager (apt, dnf, etc.)."
fi
_log "--------------------------------------------------"

exit 0