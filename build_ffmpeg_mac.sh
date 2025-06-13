#!/bin/bash
#==============================================================================
# build_ffmpeg_mac.sh
#==============================================================================
# Description:
#   This script builds FFmpeg with optimized libraries on macOS using Homebrew.
#   It compiles SVT-AV1 (AV1 encoder/decoder) and Opus (audio codec) from source
#   and links them with FFmpeg to create a high-performance media toolkit.
#
# Features:
#   - Builds FFmpeg with SVT-AV1 and Opus support
#   - Enables macOS-specific VideoToolbox hardware acceleration
#   - Installs to user's local directory (~/.local) to avoid system conflicts
#   - Uses optimized build flags for better performance
#   - Provides command-line options for customization
#
# Usage:
#   ./build_ffmpeg_mac.sh [options]
#
# Options:
#   -h, --help                 Show this help message
#   -p, --prefix PATH          Set installation prefix (default: ~/.local)
#   -b, --build-dir PATH       Set build directory (default: /tmp/ffmpeg_build_temp)
#   -c, --clean                Clean build directory before starting
#   -k, --keep                 Keep build directory after completion
#   -j, --jobs N               Set number of parallel jobs (default: auto-detect)
#   -s, --skip-deps            Skip dependency installation
#   --ffmpeg-branch BRANCH     Set FFmpeg branch (default: master)
#   --svt-branch BRANCH        Set SVT-AV1 branch (default: master)
#   --opus-branch BRANCH       Set Opus branch (default: main)

#
# Requirements:
#   - macOS with Homebrew installed
#   - Internet connection to download source code
#
#==============================================================================

#------------------------------------------------------------------------------
# Configuration Variables
#------------------------------------------------------------------------------
# Default values (can be overridden by command-line options)
INSTALL_PREFIX="$HOME/.local"        # Installation directory (user-specific)
BUILD_DIR="/tmp/ffmpeg_build_temp"   # Temporary build directory
FFMPEG_REPO="https://github.com/FFmpeg/FFmpeg.git"
FFMPEG_BRANCH="master"
SVT_AV1_REPO="https://gitlab.com/AOMediaCodec/SVT-AV1.git"  # svt-av1
#SVT_AV1_REPO="https://github.com/BlueSwordM/svt-av1-psyex.git"  # svt-av1-psyex
SVT_AV1_BRANCH="master"
OPUS_REPO="https://gitlab.xiph.org/xiph/opus.git"
OPUS_BRANCH="main"

# Build control flags
CLEAN_BUILD=false                    # Whether to clean build directory before starting
KEEP_BUILD_DIR=false                 # Whether to keep build directory after completion
SKIP_DEPS=false                      # Whether to skip dependency installation
PARALLEL_JOBS=$(sysctl -n hw.ncpu)   # Number of parallel jobs (default: auto-detect)

#------------------------------------------------------------------------------
# Helper Functions
#------------------------------------------------------------------------------
# Log function to display timestamped messages with different severity levels
_log() {
    local level="INFO"
    if [[ $# -gt 1 ]]; then
        level="$1"
        shift
    fi

    local color=""
    local reset="\033[0m"

    case "$level" in
        "INFO")    color="\033[0;32m" ;;  # Green
        "WARNING") color="\033[0;33m" ;;  # Yellow
        "ERROR")   color="\033[0;31m" ;;  # Red
        "SUCCESS") color="\033[0;36m" ;;  # Cyan
        *)         color="\033[0m"    ;;  # No color
    esac

    echo -e "${color}[$(date +'%Y-%m-%d %H:%M:%S')] [$level] $*${reset}"
}

# Log an error message and exit
_error() {
    _log "ERROR" "$*"
    exit 1
}

# Log a warning message
_warning() {
    _log "WARNING" "$*"
}

# Log a success message
_success() {
    _log "SUCCESS" "$*"
}

# Check if a required command exists in the system
check_command() {
    if ! command -v "$1" &> /dev/null; then
        _error "Required command '$1' not found. Please install it."
    fi
}



# Verify a build artifact exists
verify_artifact() {
    if [[ ! -f "$1" ]]; then
        _error "Build verification failed: $1 not found"
    fi
}

# Print help message
show_help() {
    cat << EOF
$(grep -A 40 "^# Usage:" "$0" | grep -B 40 "^# Requirements:" | grep -v "^#==")
EOF
    exit 0
}

#------------------------------------------------------------------------------
# Parse Command-Line Arguments
#------------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -h|--help)
                show_help
                ;;
            -p|--prefix)
                INSTALL_PREFIX="$2"
                shift 2
                ;;
            -b|--build-dir)
                BUILD_DIR="$2"
                STATE_FILE="$BUILD_DIR/.build_state"
                shift 2
                ;;
            -c|--clean)
                CLEAN_BUILD=true
                shift
                ;;
            -k|--keep)
                KEEP_BUILD_DIR=true
                shift
                ;;
            -j|--jobs)
                PARALLEL_JOBS="$2"
                shift 2
                ;;
            -s|--skip-deps)
                SKIP_DEPS=true
                shift
                ;;
            --ffmpeg-branch)
                FFMPEG_BRANCH="$2"
                shift 2
                ;;
            --svt-branch)
                SVT_AV1_BRANCH="$2"
                shift 2
                ;;
            --opus-branch)
                OPUS_BRANCH="$2"
                shift 2
                ;;

            *)
                _error "Unknown option: $1"
                ;;
        esac
    done
}

# Parse command-line arguments
parse_args "$@"

#------------------------------------------------------------------------------
# Enable Strict Mode & Error Handling
#------------------------------------------------------------------------------
set -euo pipefail  # Exit on error, undefined vars, and pipe failures
trap '_error "Error on line $LINENO"' ERR  # Show line number on errors

#------------------------------------------------------------------------------
# Clean or Create Build Directory
#------------------------------------------------------------------------------
if [[ $CLEAN_BUILD == true && -d "$BUILD_DIR" ]]; then
    _log "Cleaning previous build directory: $BUILD_DIR"
    rm -rf "$BUILD_DIR"
fi

# Create build directory if it doesn't exist
if [[ ! -d "$BUILD_DIR" ]]; then
    _log "Creating build directory: $BUILD_DIR"
    mkdir -p "$BUILD_DIR"
fi



#------------------------------------------------------------------------------
# macOS Setup
#------------------------------------------------------------------------------
_log "Setting up for macOS (Homebrew)"
BREW_CMD="brew"

# Verify Homebrew is installed
if ! command -v "$BREW_CMD" &> /dev/null; then
     _error "brew command ('$BREW_CMD') not found. Please install Homebrew.
Installation command: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
fi

# Verify macOS version
MAC_VERSION=$(sw_vers -productVersion)
_log "Detected macOS version: $MAC_VERSION"

# Check for minimum required macOS version (10.15 Catalina or newer recommended)
if [[ $(echo "$MAC_VERSION" | cut -d. -f1) -lt 10 || ($(echo "$MAC_VERSION" | cut -d. -f1) -eq 10 && $(echo "$MAC_VERSION" | cut -d. -f2) -lt 15) ]]; then
    _warning "Your macOS version ($MAC_VERSION) may be too old for optimal FFmpeg performance.
Recommended: macOS 10.15 Catalina or newer."
fi

_log "Using brew command: $BREW_CMD"
_log "Using parallel jobs: $PARALLEL_JOBS"

# Update Homebrew package lists (only if not skipping dependencies)
if [[ $SKIP_DEPS == false ]]; then
    _log "Updating brew..."
    "$BREW_CMD" update || _warning "Brew update failed, continuing with potentially outdated package information"
fi

#------------------------------------------------------------------------------
# Install Dependencies
#------------------------------------------------------------------------------
install_dependencies() {
    if [[ $SKIP_DEPS == true ]]; then
        _log "Skipping dependency installation as requested"
        return 0
    fi

    _log "Installing dependencies..."
    DEPS=(
        cmake       # Build system for SVT-AV1
        nasm        # Assembly compiler for optimized routines
        pkg-config  # Library detection tool
        git         # For cloning source repositories
        wget        # For downloading additional resources
        autoconf    # For Opus build system
        automake    # For Opus build system
        libtool     # For Opus build system
        llvm        # Provides clang/clang++ for SVT-AV1 optimized build
    )

    # Install each dependency if not already present
    local all_deps_installed=true
    for dep in "${DEPS[@]}"; do
        if "$BREW_CMD" list "$dep" &> /dev/null; then
            _log "$dep is already installed."
        else
            _log "Installing $dep..."
            if ! "$BREW_CMD" install "$dep"; then
                _error "Failed to install $dep. Please check your internet connection and try again."
            fi
            all_deps_installed=false
        fi
    done

    if [[ $all_deps_installed == true ]]; then
        _success "All dependencies were already installed."
    else
        _success "Dependencies installed successfully."
    fi

    # Verify critical dependencies
    check_command cmake
    check_command nasm
    check_command pkg-config
    check_command git
    check_command autoconf

    _success "Dependencies installation complete"
}

# Install dependencies
install_dependencies

#------------------------------------------------------------------------------
# Prepare Directories
#------------------------------------------------------------------------------
prepare_directories() {
    _log "Creating directories..."
    mkdir -p "$BUILD_DIR"      # Create build directory
    mkdir -p "$INSTALL_PREFIX" # Create installation directory

    # Create lib/pkgconfig directory in installation prefix
    mkdir -p "$INSTALL_PREFIX/lib/pkgconfig"

    # Remove any previous source directories
    _log "Removing any previous source directories..."
    rm -rf "$BUILD_DIR/ffmpeg"
    rm -rf "$BUILD_DIR/SVT-AV1"
    rm -rf "$BUILD_DIR/opus"
}

prepare_directories

#------------------------------------------------------------------------------
# Build SVT-AV1 from Source
#------------------------------------------------------------------------------
build_svt_av1() {
    _log "Building SVT-AV1..."

    # Clone SVT-AV1 if not already cloned
    if [[ ! -d "$BUILD_DIR/SVT-AV1" ]]; then
        _log "Cloning SVT-AV1 source (branch: $SVT_AV1_BRANCH)..."
        cd "$BUILD_DIR"
        if ! git clone --depth 1 --branch "$SVT_AV1_BRANCH" "$SVT_AV1_REPO" SVT-AV1; then
            _error "Failed to clone SVT-AV1 repository. Please check your internet connection and the branch name."
        fi
    else
        _log "Using existing SVT-AV1 source directory"
    fi

    cd "$BUILD_DIR/SVT-AV1"

    # Clean build directory if it exists
    if [[ -d "Build" ]]; then
        _log "Cleaning previous SVT-AV1 build directory"
        rm -rf Build
    fi

    _log "Configuring SVT-AV1..."
    mkdir -p Build  # Standard CMake build directory
    cd Build

    # Locate LLVM/Clang for optimized builds
    LLVM_PREFIX=$("$BREW_CMD" --prefix llvm)
    _log "Using llvm prefix: $LLVM_PREFIX"
    if [[ -z "$LLVM_PREFIX" || ! -d "$LLVM_PREFIX/bin" ]]; then
        _error "Could not find llvm prefix or its bin directory. Ensure llvm is installed correctly."
    fi

    # Set paths to Clang compilers
    CLANG_PATH="$LLVM_PREFIX/bin/clang"
    CLANGPP_PATH="$LLVM_PREFIX/bin/clang++"
    if [[ ! -x "$CLANG_PATH" || ! -x "$CLANGPP_PATH" ]]; then
        _error "clang ($CLANG_PATH) or clang++ ($CLANGPP_PATH) not found or not executable in llvm prefix."
    fi
    _log "Using clang: $CLANG_PATH"
    _log "Using clang++: $CLANGPP_PATH"

    # Configure SVT-AV1 with optimized settings
    if ! cmake .. \
        -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
        -DCMAKE_C_COMPILER="$CLANG_PATH" \
        -DCMAKE_CXX_COMPILER="$CLANGPP_PATH" \
        -DBUILD_SHARED_LIBS=ON \
        -DCMAKE_BUILD_TYPE=Release \
        -DBUILD_APPS=OFF \
        -DSVT_AV1_LTO=ON \
        -DNATIVE=ON \
        -DCMAKE_C_FLAGS="-O3 -march=native -mtune=native" \
        -DCMAKE_CXX_FLAGS="-O3 -march=native -mtune=native"; then
        _error "SVT-AV1 configuration failed"
    fi

    # Build and install SVT-AV1
    _log "Building SVT-AV1 (using $PARALLEL_JOBS parallel jobs)..."
    if ! make -j"$PARALLEL_JOBS"; then
        _error "SVT-AV1 build failed"
    fi

    _log "Installing SVT-AV1..."
    if ! make install; then
        _error "SVT-AV1 installation failed"
    fi

    # Verify installation - only check for encoder as decoder might not be built
    verify_artifact "$INSTALL_PREFIX/lib/libSvtAv1Enc.dylib"

    _success "SVT-AV1 installation complete"


}

# Build SVT-AV1
build_svt_av1

#------------------------------------------------------------------------------
# Build Opus from Source
#------------------------------------------------------------------------------
build_opus() {
    _log "Building Opus..."

    # Clone Opus if not already cloned
    if [[ ! -d "$BUILD_DIR/opus" ]]; then
        _log "Cloning Opus source (branch: $OPUS_BRANCH)..."
        cd "$BUILD_DIR"
        if ! git clone --depth 1 --branch "$OPUS_BRANCH" "$OPUS_REPO" opus; then
            _error "Failed to clone Opus repository. Please check your internet connection and the branch name."
        fi
    else
        _log "Using existing Opus source directory"
    fi

    cd "$BUILD_DIR/opus"

    # Clean any previous build artifacts
    if [[ -f "Makefile" ]]; then
        _log "Cleaning previous Opus build"
        make distclean || true
    fi

    _log "Configuring Opus..."
    if ! ./autogen.sh; then
        _error "Opus autogen.sh failed"
    fi

    # Configure with optimized settings
    if ! ./configure \
        --prefix="$INSTALL_PREFIX" \
        --disable-static \
        --enable-shared \
        --disable-doc \
        --disable-extra-programs \
        CFLAGS="-O3 -march=native -mtune=native"; then
        _error "Opus configuration failed"
    fi

    # Build and install Opus
    _log "Building Opus (using $PARALLEL_JOBS parallel jobs)..."
    if ! make -j"$PARALLEL_JOBS"; then
        _error "Opus build failed"
    fi

    _log "Installing Opus..."
    if ! make install; then
        _error "Opus installation failed"
    fi

    # Verify installation
    verify_artifact "$INSTALL_PREFIX/lib/libopus.dylib"

    _success "Opus installation complete"


}

# Build Opus
build_opus


#------------------------------------------------------------------------------
# Build FFmpeg
#------------------------------------------------------------------------------
build_ffmpeg() {
    _log "Building FFmpeg..."

    # Clone FFmpeg if not already cloned
    if [[ ! -d "$BUILD_DIR/ffmpeg" ]]; then
        _log "Cloning FFmpeg source (branch: $FFMPEG_BRANCH)..."
        cd "$BUILD_DIR"
        if ! git clone --depth 1 --branch "$FFMPEG_BRANCH" "$FFMPEG_REPO" ffmpeg; then
            _error "Failed to clone FFmpeg repository. Please check your internet connection and the branch name."
        fi
    else
        _log "Using existing FFmpeg source directory"
    fi

    cd "$BUILD_DIR/ffmpeg"

    # Clean any previous build artifacts
    if [[ -f "Makefile" ]]; then
        _log "Cleaning previous FFmpeg build"
        make distclean || true
    fi

    # Set pkg-config path to find our custom-built libraries
    export PKG_CONFIG_PATH="${INSTALL_PREFIX}/lib/pkgconfig:${PKG_CONFIG_PATH:-}"
    _log "PKG_CONFIG_PATH set to: $PKG_CONFIG_PATH"

    # Verify that our custom libraries are found
    if ! pkg-config --exists SvtAv1Enc; then
        _error "SVT-AV1 encoder not found by pkg-config. Check that it was installed correctly."
    fi

    if ! pkg-config --exists opus; then
        _error "Opus not found by pkg-config. Check that it was installed correctly."
    fi

    # Configure macOS-specific options
    FFMPEG_EXTRA_FLAGS=""
    EXTRA_LDFLAGS_VAL=""
    EXTRA_CFLAGS_VAL="-O3 -march=native -mtune=native"

    # Enable macOS hardware acceleration
    _log "macOS detected: Enabling VideoToolbox support."
    FFMPEG_EXTRA_FLAGS="--enable-videotoolbox"

    # Add runtime path to find libraries in custom location
    EXTRA_LDFLAGS_VAL="-Wl,-rpath,${INSTALL_PREFIX}/lib"

    # Build FFmpeg configuration arguments
    CONFIGURE_ARGS=(
        --prefix="$INSTALL_PREFIX"
        --disable-static
        --enable-shared
        --enable-gpl                # Enable GPL components
        --enable-libsvtav1          # Enable SVT-AV1 support (encoder only)
        --enable-libopus            # Enable Opus audio codec
        --enable-nonfree            # Allow nonfree components
        --enable-pthreads           # Enable threading support
        --enable-hardcoded-tables   # Optimize for speed
        --disable-debug             # Disable debug symbols
        --disable-doc               # Don't build documentation
        --disable-htmlpages         # Don't build HTML documentation
        --disable-manpages          # Don't build man pages
        --disable-podpages          # Don't build POD documentation
        --disable-txtpages          # Don't build text documentation
        --extra-cflags="$EXTRA_CFLAGS_VAL"
    )

    # Add platform-specific flags to configuration
    if [[ -n "$EXTRA_LDFLAGS_VAL" ]]; then
        CONFIGURE_ARGS+=(--extra-ldflags="$EXTRA_LDFLAGS_VAL")
    fi
    if [[ -n "$FFMPEG_EXTRA_FLAGS" ]]; then
        # Split FFMPEG_EXTRA_FLAGS in case it contains multiple flags
        read -ra flags <<< "$FFMPEG_EXTRA_FLAGS"
        CONFIGURE_ARGS+=("${flags[@]}")
    fi

    # Run FFmpeg configure script
    _log "Executing configure with arguments:"
    printf "  %s\n" "${CONFIGURE_ARGS[@]}"
    if ! ./configure "${CONFIGURE_ARGS[@]}"; then
        _error "FFmpeg configuration failed"
    fi

    _log "FFmpeg configuration complete."

    # Build and install FFmpeg
    _log "Building FFmpeg (using $PARALLEL_JOBS parallel jobs)..."
    if ! make -j"$PARALLEL_JOBS"; then
        _error "FFmpeg build failed"
    fi

    _log "Build complete. Installing FFmpeg..."
    if ! make install; then
        _error "FFmpeg installation failed"
    fi

    # Verify installation
    verify_artifact "$INSTALL_PREFIX/bin/ffmpeg"
    verify_artifact "$INSTALL_PREFIX/bin/ffprobe"

    _success "FFmpeg installation complete"


}

# Build FFmpeg
build_ffmpeg

#------------------------------------------------------------------------------
# Verify Installation
#------------------------------------------------------------------------------
verify_installation() {
    _log "Verifying installation..."

    # Check for FFmpeg binaries
    if [[ ! -x "$INSTALL_PREFIX/bin/ffmpeg" ]]; then
        _error "FFmpeg binary not found or not executable"
    fi

    if [[ ! -x "$INSTALL_PREFIX/bin/ffprobe" ]]; then
        _error "FFprobe binary not found or not executable"
    fi

    # Check FFmpeg version and enabled components
    _log "FFmpeg version information:"
    "$INSTALL_PREFIX/bin/ffmpeg" -version | head -n 3

    # Check for SVT-AV1 support
    if ! "$INSTALL_PREFIX/bin/ffmpeg" -hide_banner -encoders | grep -q "libsvtav1"; then
        _warning "SVT-AV1 encoder not found in FFmpeg"
    else
        _success "SVT-AV1 encoder available"
    fi

    # Check for Opus support
    if ! "$INSTALL_PREFIX/bin/ffmpeg" -hide_banner -encoders | grep -q "libopus"; then
        _warning "Opus encoder not found in FFmpeg"
    else
        _success "Opus encoder available"
    fi

    # Check for VideoToolbox support
    if ! "$INSTALL_PREFIX/bin/ffmpeg" -hide_banner -encoders | grep -q "videotoolbox"; then
        _warning "VideoToolbox encoder not found in FFmpeg"
    else
        _success "VideoToolbox encoder available"
    fi

    _success "Installation verification complete"
}

# Verify the installation
verify_installation

#------------------------------------------------------------------------------
# Cleanup and Final Message
#------------------------------------------------------------------------------
cleanup() {
    if [[ $KEEP_BUILD_DIR == false ]]; then
        _log "Cleaning up build directory..."
        rm -rf "$BUILD_DIR"
        _log "Build directory removed"
    else
        _log "Build directory $BUILD_DIR kept as requested"
    fi
}

# Perform cleanup
cleanup

# Print final message
_success "--------------------------------------------------"
_success "FFmpeg build successful!"
_success "ffmpeg and ffprobe are located at: $INSTALL_PREFIX/bin/"
_success "--------------------------------------------------"
_log "To use FFmpeg, add the following to your PATH:"
_log "  export PATH=\"$INSTALL_PREFIX/bin:\$PATH\""
_log "You may want to add this to your ~/.bashrc or ~/.zshrc file"

exit 0
