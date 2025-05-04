#!/bin/bash

# build_ffmpeg.sh
# Builds FFmpeg binaries on macOS (Homebrew) or Debian (Linuxbrew)
# Includes: libsvtav1, libopus

# --- Configuration ---
INSTALL_PREFIX="$HOME/.local" # Install into user's local directory
BUILD_DIR="/tmp/ffmpeg_build_temp"
FFMPEG_REPO="https://github.com/FFmpeg/FFmpeg.git"
FFMPEG_BRANCH="master"
#SVT_AV1_REPO="https://gitlab.com/AOMediaCodec/SVT-AV1.git" # svt-av1
SVT_AV1_REPO="https://github.com/BlueSwordM/svt-av1-psyex.git" # svt-av1-psyex
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
# if [ -d "$INSTALL_PREFIX" ]; then # DO NOT remove /usr/local
#     _log "Removing previous install directory: $INSTALL_PREFIX"
#     # rm -rf "$INSTALL_PREFIX" # DO NOT remove /usr/local
# fi

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
    llvm # Provides clang/clang++, required for SVT-AV1 build
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
# --- Install Linux-specific Dependencies ---
if [[ "$OS_NAME" == "Linux" ]]; then
    _log "Installing Linux-specific dependencies..."
    LINUX_DEPS=(
        vulkan-headers
        vulkan-loader
    )
    for dep in "${LINUX_DEPS[@]}"; do
        if "$BREW_CMD" list "$dep" &> /dev/null; then
            _log "$dep is already installed."
        else
            _log "Installing $dep..."
            if "$BREW_CMD" install "$dep"; then
                 _log "Successfully installed $dep."
            else
                 _log "Warning: Failed to install $dep via brew."
                 _log "         Vulkan support might not be enabled correctly."
                 _log "         Please install it manually (e.g., using your system package manager like apt or dnf) and ensure pkg-config can find 'vulkan'."
                 # Decide if we should exit here or just warn. Warning seems better.
            fi
        fi
    done
    _log "Linux-specific dependencies check complete."
fi

# --- Environment Configuration ---
# No custom environment needed for standard /usr/local shared build
_log "Using standard build environment for /usr/local installation."

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
# Get the path to the installed llvm to find clang
LLVM_PREFIX=$("$BREW_CMD" --prefix llvm)
_log "Using llvm prefix: $LLVM_PREFIX"
if [[ -z "$LLVM_PREFIX" || ! -d "$LLVM_PREFIX/bin" ]]; then
    _log "Error: Could not find llvm prefix or its bin directory. Ensure llvm is installed correctly."
    exit 1
fi
CLANG_PATH="$LLVM_PREFIX/bin/clang"
CLANGPP_PATH="$LLVM_PREFIX/bin/clang++"
if [[ ! -x "$CLANG_PATH" || ! -x "$CLANGPP_PATH" ]]; then
    _log "Error: clang ($CLANG_PATH) or clang++ ($CLANGPP_PATH) not found or not executable in llvm prefix."
    exit 1
fi
_log "Using clang: $CLANG_PATH"
_log "Using clang++: $CLANGPP_PATH"

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


# --- Download FFmpeg ---
_log "Downloading FFmpeg source (branch: $FFMPEG_BRANCH)..."
cd "$BUILD_DIR" # Go back to build dir
git clone --depth 1 --branch "$FFMPEG_BRANCH" "$FFMPEG_REPO" ffmpeg
cd ffmpeg

# Ensure pkg-config finds the libraries installed in the custom prefix
export PKG_CONFIG_PATH="${INSTALL_PREFIX}/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
_log "PKG_CONFIG_PATH set to: $PKG_CONFIG_PATH"

# --- Add OS-specific flags ---
FFMPEG_EXTRA_FLAGS=""
EXTRA_CFLAGS_VAL="" # Use different var names to avoid confusion
EXTRA_LDFLAGS_VAL=""
if [[ "$OS_NAME" == "Linux" ]]; then
    _log "Linux detected: Checking for Vulkan support..."
    # Dependencies are now installed earlier if needed.
    # Now check if pkg-config can find vulkan after potential installation
    if pkg-config --exists vulkan; then
        _log "Vulkan SDK found via pkg-config. Enabling Vulkan support and adding paths."
        FFMPEG_EXTRA_FLAGS="--enable-vulkan"
        # Explicitly provide paths for configure script
        VULKAN_HEADERS_PREFIX=$("$BREW_CMD" --prefix vulkan-headers)
        VULKAN_LOADER_PREFIX=$("$BREW_CMD" --prefix vulkan-loader)
        if [[ -n "$VULKAN_HEADERS_PREFIX" && -d "$VULKAN_HEADERS_PREFIX/include" ]]; then
             EXTRA_CFLAGS_VAL+="-I${VULKAN_HEADERS_PREFIX}/include" # No leading/trailing space needed here
             _log "Adding Vulkan include path: ${EXTRA_CFLAGS_VAL}"
        else
            _log "Warning: Could not find vulkan-headers include directory via brew prefix."
        fi
        if [[ -n "$VULKAN_LOADER_PREFIX" && -d "$VULKAN_LOADER_PREFIX/lib" ]]; then
             EXTRA_LDFLAGS_VAL+="-L${VULKAN_LOADER_PREFIX}/lib" # No leading/trailing space needed here
             _log "Adding Vulkan library path: ${EXTRA_LDFLAGS_VAL}"
        else
             _log "Warning: Could not find vulkan-loader lib directory via brew prefix."
        fi
    else
        _log "Warning: Vulkan SDK not found via pkg-config even after attempting install. Skipping --enable-vulkan."
        _log "         Ensure Vulkan development libraries are installed and discoverable by pkg-config."
    fi

    # Add rpath to LDFLAGS, ensuring space if Vulkan flags were added
    # This should be INSIDE the Linux block
    if [[ -n "$EXTRA_LDFLAGS_VAL" ]]; then
        EXTRA_LDFLAGS_VAL+=" " # Add space separator if Vulkan flags were added
    fi
elif [[ "$OS_NAME" == "Darwin" ]]; then
    _log "macOS detected: Enabling VideoToolbox support."
    FFMPEG_EXTRA_FLAGS="--enable-videotoolbox"
fi # End of OS-specific block

# Add rpath to LDFLAGS for both Linux and macOS to find libs in INSTALL_PREFIX
if [[ -n "$EXTRA_LDFLAGS_VAL" ]]; then
    EXTRA_LDFLAGS_VAL+=" " # Add space separator if needed (e.g., after Linux Vulkan flags)
fi
EXTRA_LDFLAGS_VAL+="-Wl,-rpath,${INSTALL_PREFIX}/lib"

# --- Build configure arguments array ---
CONFIGURE_ARGS=(
    --prefix="$INSTALL_PREFIX"
    --disable-static
    --enable-shared
    --enable-gpl
    --enable-libsvtav1
    --enable-libopus
    --disable-xlib
    --disable-libxcb
    --disable-vaapi
    --disable-vdpau
    --disable-libdrm
)

# Add conditional flags to the array
if [[ -n "$EXTRA_CFLAGS_VAL" ]]; then
    CONFIGURE_ARGS+=(--extra-cflags="$EXTRA_CFLAGS_VAL")
fi
if [[ -n "$EXTRA_LDFLAGS_VAL" ]]; then
    CONFIGURE_ARGS+=(--extra-ldflags="$EXTRA_LDFLAGS_VAL")
fi
if [[ -n "$FFMPEG_EXTRA_FLAGS" ]]; then
    # Split FFMPEG_EXTRA_FLAGS in case it contains multiple flags in the future
    read -ra flags <<< "$FFMPEG_EXTRA_FLAGS"
    CONFIGURE_ARGS+=("${flags[@]}")
fi

# --- Execute configure ---
_log "Executing configure with arguments:"
printf "  %s\n" "${CONFIGURE_ARGS[@]}" # Log arguments for debugging
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
