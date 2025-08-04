#!/bin/bash

# build_ffmpeg_debian.sh
# Builds FFmpeg binaries on Debian Linux
# Includes: libsvtav1, libopus, libdav1d, libx265, libzimg

# --- Configuration ---
INSTALL_PREFIX="$HOME/.local" # Install into user's local directory
BUILD_DIR="/tmp/ffmpeg_build_temp"
FFMPEG_REPO="https://github.com/FFmpeg/FFmpeg.git"
FFMPEG_BRANCH="master"
SVT_AV1_REPO="https://gitlab.com/AOMediaCodec/SVT-AV1.git" # svt-av1
#SVT_AV1_REPO="https://github.com/BlueSwordM/svt-av1-psyex.git" # svt-av1-psyex
SVT_AV1_BRANCH="master"
OPUS_REPO="https://github.com/xiph/opus.git"
OPUS_BRANCH="main"
DAV1D_REPO="https://code.videolan.org/videolan/dav1d.git"
DAV1D_BRANCH="master"
X265_REPO="https://bitbucket.org/multicoreware/x265_git.git"
X265_BRANCH="master"
ZIMG_REPO="https://github.com/sekrit-twc/zimg.git"
ZIMG_BRANCH="master"

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
# if [ -d "$INSTALL_PREFIX" ]; then # DO NOT remove /usr/local
#     _log "Removing previous install directory: $INSTALL_PREFIX"
#     # rm -rf "$INSTALL_PREFIX" # DO NOT remove /usr/local
# fi

# --- Strict Mode & Error Handling ---
set -euo pipefail
trap 'echo "Error on line $LINENO"; exit 1' ERR

# --- OS Detection & Setup ---
OS_NAME=$(uname -s)

_log "Detected OS: $OS_NAME"

if [[ "$OS_NAME" == "Linux" ]]; then
    if [[ -f /etc/debian_version ]]; then
        _log "Debian detected."
        CPU_COUNT=$(nproc)

        # --- Install Dependencies via apt ---
        _log "Checking/installing required Debian packages via apt..."
        REQUIRED_PKGS=(
            build-essential # Common build tools (make, gcc, etc.)
            cmake
            nasm
            yasm # Often needed by FFmpeg assembly
            pkg-config
            git
            wget
            autoconf
            automake
            libtool
            clang # Use system clang
            libva-dev
            libva-drm2
            libva-x11-2
            libva2
            meson # Required for dav1d
            ninja-build # Required for dav1d
        )
        PACKAGES_TO_INSTALL=()
        for pkg in "${REQUIRED_PKGS[@]}"; do
            if dpkg -s "$pkg" &> /dev/null; then
                _log "$pkg is already installed."
            else
                _log "$pkg is NOT installed."
                PACKAGES_TO_INSTALL+=("$pkg")
            fi
        done

        if [ ${#PACKAGES_TO_INSTALL[@]} -gt 0 ]; then
            _log "The following required Debian packages are missing: ${PACKAGES_TO_INSTALL[*]}"
            if command -v sudo &> /dev/null; then
                 _log "Attempting to install missing packages using: sudo apt update && sudo apt install -y ${PACKAGES_TO_INSTALL[*]}"
                 # Run non-interactively if possible
                 export DEBIAN_FRONTEND=noninteractive
                 if sudo apt update && sudo apt install -y "${PACKAGES_TO_INSTALL[@]}"; then
                      _log "Successfully installed missing Debian packages."
                 else
                      _log "Error: Failed to install required Debian packages using apt. Please install them manually."
                      exit 1
                 fi
            else
                 _log "Error: sudo command not found. Please install the following packages manually using apt: ${PACKAGES_TO_INSTALL[*]}"
                 exit 1
            fi
        fi
        _log "Required Debian packages check complete."

    else
        _log "Error: Non-Debian Linux detected. This script now requires Debian/apt."
        exit 1
    fi
else
    _log "Error: Unsupported operating system '$OS_NAME'."
    exit 1
fi

_log "Using CPU cores: $CPU_COUNT"

# --- Environment Configuration ---
# No custom environment needed for standard shared build
_log "Using standard build environment for $INSTALL_PREFIX installation."

# --- Prepare Directories ---
_log "Creating directories..."
mkdir -p "$BUILD_DIR"
mkdir -p "$INSTALL_PREFIX"
rm -rf "$BUILD_DIR/ffmpeg" # Clean previous ffmpeg source attempt
rm -rf "$BUILD_DIR/SVT-AV1" # Clean previous svt-av1 source attempt
rm -rf "$BUILD_DIR/opus" # Clean previous opus source attempt
rm -rf "$BUILD_DIR/dav1d" # Clean previous dav1d source attempt
rm -rf "$BUILD_DIR/x265" # Clean previous x265 source attempt
rm -rf "$BUILD_DIR/zimg" # Clean previous zimg source attempt

# --- Build SVT-AV1 from Source ---
_log "Cloning SVT-AV1 source (branch: $SVT_AV1_BRANCH)..."
cd "$BUILD_DIR"
git clone --depth 1 --branch "$SVT_AV1_BRANCH" "$SVT_AV1_REPO" SVT-AV1
cd SVT-AV1

_log "Configuring SVT-AV1..."
mkdir -p Build # Use standard CMake build directory convention
cd Build
# Use system clang/clang++ (should be in PATH after installing build-essential/clang)
_log "Using system clang/clang++"
CLANG_PATH=$(command -v clang)
CLANGPP_PATH=$(command -v clang++)
if [[ ! -x "$CLANG_PATH" || ! -x "$CLANGPP_PATH" ]]; then
    _log "Error: clang or clang++ not found in PATH. Ensure 'clang' package is installed correctly."
    exit 1
fi

cmake .. \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    -DCMAKE_C_COMPILER="$CLANG_PATH" \
    -DCMAKE_CXX_COMPILER="$CLANGPP_PATH" \
    -DBUILD_SHARED_LIBS=ON \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_APPS=OFF \
    -DSVT_AV1_LTO=ON \
    -DNATIVE=ON \
    -DCMAKE_C_FLAGS="-O3" \
    -DCMAKE_CXX_FLAGS="-O3" # We only need the library, add PSY optimizations

_log "Building SVT-AV1 (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Installing SVT-AV1..."
make install # No sudo needed for $HOME/.local
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
    --disable-static \
    --enable-shared \
    --disable-doc \
    --disable-extra-programs

_log "Building opus (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Installing opus..."
make install # No sudo needed for $HOME/.local
_log "opus installation complete."

# --- Build dav1d from Source ---
_log "Cloning dav1d source (branch: $DAV1D_BRANCH)..."
cd "$BUILD_DIR"
git clone --depth 1 --branch "$DAV1D_BRANCH" "$DAV1D_REPO" dav1d
cd dav1d

_log "Configuring dav1d..."
mkdir -p build
cd build
meson setup .. \
    --prefix="$INSTALL_PREFIX" \
    --buildtype=release \
    --default-library=shared \
    -Denable_tools=false \
    -Denable_tests=false

_log "Building dav1d (using $CPU_COUNT cores)..."
ninja -j"$CPU_COUNT"
_log "Installing dav1d..."
ninja install # No sudo needed for $HOME/.local
_log "dav1d installation complete."

# --- Build x265 from Source ---
_log "Cloning x265 source (branch: $X265_BRANCH)..."
cd "$BUILD_DIR"
git clone --depth 1 --branch "$X265_BRANCH" "$X265_REPO" x265
cd x265/build/linux

_log "Configuring x265..."
cmake -G "Unix Makefiles" ../../source \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    -DCMAKE_BUILD_TYPE=Release \
    -DENABLE_SHARED=ON \
    -DSTATIC_LINK_CRT=OFF \
    -DENABLE_CLI=OFF \
    -DENABLE_LIBNUMA=OFF \
    -DENABLE_HDR10_PLUS=ON

_log "Building x265 (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Installing x265..."
make install # No sudo needed for $HOME/.local

# x265 doesn't always create a proper pkg-config file, so we create one
_log "Creating x265 pkg-config file..."
mkdir -p "$INSTALL_PREFIX/lib/pkgconfig"

# Get the actual version from x265_config.h
X265_VERSION=$(grep "X265_VERSION_STR" "$INSTALL_PREFIX/include/x265_config.h" | cut -d'"' -f2 | head -1) || X265_VERSION="3.6"

cat > "$INSTALL_PREFIX/lib/pkgconfig/x265.pc" << EOF
prefix=$INSTALL_PREFIX
exec_prefix=\${prefix}
libdir=\${exec_prefix}/lib
includedir=\${prefix}/include

Name: x265
Description: H.265/HEVC video encoder
Version: $X265_VERSION
Libs: -L\${libdir} -lx265
Libs.private: -lstdc++ -lm -lpthread -ldl -lrt
Cflags: -I\${includedir}
EOF

_log "x265 installation complete."

# --- Build zimg from Source ---
_log "Cloning zimg source (branch: $ZIMG_BRANCH)..."
cd "$BUILD_DIR"
git clone --depth 1 --branch "$ZIMG_BRANCH" "$ZIMG_REPO" zimg
cd zimg

# Initialize submodules (required for zimg build)
_log "Initializing zimg submodules..."
git submodule update --init --recursive

_log "Configuring zimg..."
./autogen.sh
./configure \
    --prefix="$INSTALL_PREFIX" \
    --disable-static \
    --enable-shared

_log "Building zimg (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Installing zimg..."
make install # No sudo needed for $HOME/.local
_log "zimg installation complete."


# --- Download FFmpeg ---
_log "Downloading FFmpeg source (branch: $FFMPEG_BRANCH)..."
cd "$BUILD_DIR" # Go back to build dir
git clone --depth 1 --branch "$FFMPEG_BRANCH" "$FFMPEG_REPO" ffmpeg
cd ffmpeg

# Ensure pkg-config finds the libraries installed in the custom prefix
# Ensure pkg-config finds libraries installed in our custom prefix
# Explicitly add system pkgconfig path and custom prefix path
SYSTEM_PKGCONFIG_PATH="/usr/lib/x86_64-linux-gnu/pkgconfig:/usr/share/pkgconfig" # Common system paths
# Include both standard and architecture-specific paths for the custom prefix
export PKG_CONFIG_PATH="${INSTALL_PREFIX}/lib/x86_64-linux-gnu/pkgconfig:${INSTALL_PREFIX}/lib/pkgconfig:${SYSTEM_PKGCONFIG_PATH}:${PKG_CONFIG_PATH:-}"
_log "PKG_CONFIG_PATH set to: $PKG_CONFIG_PATH"
# Also ensure PKG_CONFIG points to the system version if it exists
if command -v /usr/bin/pkg-config &> /dev/null; then
    export PKG_CONFIG=/usr/bin/pkg-config
    _log "Explicitly using PKG_CONFIG=$PKG_CONFIG"
else
    _log "Warning: /usr/bin/pkg-config not found, relying on default pkg-config in PATH."
fi

# --- Add VAAPI support if available ---
FFMPEG_EXTRA_FLAGS=""
EXTRA_LDFLAGS_VAL=""
_log "Checking for VAAPI support..."
if command -v pkg-config &> /dev/null && pkg-config --exists libva; then
    _log "System VAAPI found via pkg-config. Enabling VAAPI support."
    FFMPEG_EXTRA_FLAGS="--enable-vaapi"
else
    _log "Warning: System VAAPI not found via pkg-config. Skipping --enable-vaapi."
    _log "         Ensure 'libva-dev' (or equivalent) is installed via apt."
fi

# Add rpath to LDFLAGS to find libs in INSTALL_PREFIX
EXTRA_LDFLAGS_VAL="-Wl,-rpath,${INSTALL_PREFIX}/lib:${INSTALL_PREFIX}/lib/x86_64-linux-gnu"

# --- Build configure arguments array ---
CONFIGURE_ARGS=(
    --prefix="$INSTALL_PREFIX"
    --disable-static
    --enable-shared
    --enable-gpl
    --enable-libsvtav1
    --enable-libopus
    --enable-libdav1d
    --enable-libx265
    --enable-libzimg
    --disable-xlib
    --disable-libxcb
    --disable-vdpau
    --disable-libdrm
)

# Add LDFLAGS to the array
CONFIGURE_ARGS+=(--extra-ldflags="$EXTRA_LDFLAGS_VAL")
if [[ -n "$FFMPEG_EXTRA_FLAGS" ]]; then
    # Split FFMPEG_EXTRA_FLAGS in case it contains multiple flags in the future
    read -ra flags <<< "$FFMPEG_EXTRA_FLAGS"
    CONFIGURE_ARGS+=("${flags[@]}")
fi

# --- Execute configure ---
_log "Executing configure with arguments:"
printf "  %s\n" "${CONFIGURE_ARGS[@]}" # Log arguments for debugging
# PKG_CONFIG should be set correctly above or found in PATH
./configure "${CONFIGURE_ARGS[@]}"

_log "FFmpeg configuration complete."

# --- Build and Install ---
_log "Building FFmpeg (using $CPU_COUNT cores)..."
make -j"$CPU_COUNT"
_log "Build complete. Installing FFmpeg..."
make install # No sudo needed for $HOME/.local
_log "Installation complete."

# --- Validate Static Linking ---
# Removed static linking validation for shared build

# --- Cleanup ---
_log "Cleaning up build directory..."
# cd "$HOME" # Go back home before removing build dir
# rm -rf "$BUILD_DIR"
_log "Build directory $BUILD_DIR kept for inspection. Remove manually if desired."

# --- Final Message ---
_log "--------------------------------------------------"
_log "FFmpeg build successful!"
_log "ffmpeg and ffprobe are located at: $INSTALL_PREFIX/bin/"
_log "--------------------------------------------------"

exit 0
