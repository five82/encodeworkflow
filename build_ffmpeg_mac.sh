#!/usr/bin/env bash

# Build ffmpeg with dynamic linking for macOS

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Parse command line arguments
ENABLE_LOGGING=false
for arg in "$@"; do
    case $arg in
        --log)
            ENABLE_LOGGING=true
            shift
            ;;
    esac
done

# Set up logging if --log flag is passed
if [[ "$ENABLE_LOGGING" == "true" ]]; then
    LOG_FILE="${SCRIPT_DIR}/ffmpeg_build_mac.log"
    exec 1> >(tee -a "${LOG_FILE}")
    exec 2>&1
    echo "Build started at $(date)"
    echo "======================="
fi

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check and install Homebrew dependencies
check_brew_deps() {
    local missing_deps=()
    local required_pkgs=(
        # Build tools
        "autoconf"
        "automake"
        "libtool"
        "pkg-config"
        "git"
        "cmake"
        "ninja"
        "nasm"
        "yasm"
        
        # Required libraries
        "opus"
        "dav1d"
    )

    echo "Checking Homebrew dependencies..."
    for pkg in "${required_pkgs[@]}"; do
        if ! brew list "$pkg" >/dev/null 2>&1; then
            missing_deps+=("$pkg")
        else
            echo "Found ${pkg}: $(brew list --versions ${pkg})"
        fi
    done

    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo "Missing required packages:"
        printf '%s\n' "${missing_deps[@]}"
        read -p "Would you like to install them now? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            brew install "${missing_deps[@]}"
        else
            echo "Cannot proceed without required packages."
            exit 1
        fi
    fi
}

# Check system dependencies
check_dependencies() {
    if ! command_exists brew; then
        echo "Error: Homebrew is not installed. Please install it first."
        echo "Visit https://brew.sh for installation instructions"
        exit 1
    fi
    
    check_brew_deps
    
    echo "All required dependencies are installed."
    echo "Using Homebrew from: $(brew --prefix)"
}

# Create build directories
BUILD_DIR="${SCRIPT_DIR}/ffmpeg_build"
INSTALL_DIR="${SCRIPT_DIR}/ffmpeg_install"
mkdir -p "${BUILD_DIR}" "${INSTALL_DIR}"

# Check dependencies before starting
check_dependencies

cd "${BUILD_DIR}"

# Build SVT-AV1 from source
echo "Building SVT-AV1 from source..."
if [ -d "SVT-AV1" ]; then
    rm -rf "SVT-AV1"
fi

git clone --depth=1 https://gitlab.com/AOMediaCodec/SVT-AV1.git
cd SVT-AV1
mkdir -p build
cd build

cmake .. \
    -GNinja \
    -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=ON

ninja
ninja install

# Add SVT-AV1 to pkg-config path
export PKG_CONFIG_PATH="${INSTALL_DIR}/lib/pkgconfig:${PKG_CONFIG_PATH}"

# After building SVT-AV1, add these lines to fix the library installation
echo "Fixing SVT-AV1 library installation..."
install_name_tool -id "@rpath/libSvtAv1Enc.2.dylib" "${INSTALL_DIR}/lib/libSvtAv1Enc.2.dylib"

# Before configuring FFmpeg, add these environment variables
export DYLD_LIBRARY_PATH="${INSTALL_DIR}/lib:${DYLD_LIBRARY_PATH}"
export LIBRARY_PATH="${INSTALL_DIR}/lib:${LIBRARY_PATH}"

# Build FFmpeg
cd "${BUILD_DIR}"
if [ -d "FFmpeg" ]; then
    rm -rf "FFmpeg"
fi

git clone --depth=1 https://github.com/FFmpeg/FFmpeg.git
cd FFmpeg

# Add these environment variables before FFmpeg configuration
export MACOSX_DEPLOYMENT_TARGET=10.15
export CFLAGS="-I${INSTALL_DIR}/include -O3"
export LDFLAGS="-L${INSTALL_DIR}/lib"

# Configure FFmpeg
./configure \
    --prefix="${INSTALL_DIR}" \
    --enable-gpl \
    --enable-version3 \
    --enable-shared \
    --disable-static \
    --enable-videotoolbox \
    --enable-audiotoolbox \
    --enable-libdav1d \
    --enable-libopus \
    --enable-libsvtav1 \
    --disable-doc \
    --disable-debug \
    --disable-ffplay \
    --enable-ffprobe \
    --disable-network \
    --disable-protocols \
    --enable-protocol=file \
    --pkg-config-flags="--static" \
    --extra-cflags="${CFLAGS}" \
    --extra-ldflags="${LDFLAGS} -Wl,-rpath,${INSTALL_DIR}/lib" \
    --extra-libs="-lpthread -lm" \
    --cc=clang || {
        echo "FFmpeg configure failed. Checking config.log..."
        cat ffbuild/config.log
        exit 1
    }

# Build using available CPU cores
NPROC=$(sysctl -n hw.ncpu)
make -j"${NPROC}"
make install

# After make install, add these lines to fix library paths
echo "Fixing library paths..."
for lib in "${INSTALL_DIR}"/lib/*.dylib; do
    if [ -f "$lib" ]; then
        install_name_tool -id "@rpath/$(basename $lib)" "$lib"
        install_name_tool -add_rpath "${INSTALL_DIR}/lib" "$lib"
    fi
done

for bin in "${INSTALL_DIR}"/bin/*; do
    if [ -f "$bin" ] && [ -x "$bin" ]; then
        install_name_tool -add_rpath "${INSTALL_DIR}/lib" "$bin"
        install_name_tool -add_rpath "@executable_path/../lib" "$bin"
    fi
done

# Copy and fix binaries
echo "Copying and fixing binaries..."
cp "${INSTALL_DIR}/bin/ffmpeg" "${SCRIPT_DIR}/ffmpeg"
cp "${INSTALL_DIR}/bin/ffprobe" "${SCRIPT_DIR}/ffprobe"

install_name_tool -add_rpath "@executable_path/ffmpeg_install/lib" "${SCRIPT_DIR}/ffmpeg"
install_name_tool -add_rpath "@executable_path/ffmpeg_install/lib" "${SCRIPT_DIR}/ffprobe"

# Validation steps
echo "Validating FFmpeg build..."

# Test FFmpeg execution with detailed error output
if ! "${INSTALL_DIR}/bin/ffmpeg" -version > ffmpeg_test.log 2>&1; then
    echo "Error: FFmpeg binary test failed"
    echo "Error output:"
    cat ffmpeg_test.log
    # Check dynamic library dependencies
    echo "Checking dynamic library dependencies:"
    otool -L "${INSTALL_DIR}/bin/ffmpeg"
    exit 1
fi

# Print library versions and configuration
echo "Checking library versions..."
echo "SVT-AV1:"
pkg-config --modversion SvtAv1Enc
echo "Opus:"
pkg-config --modversion opus
echo "dav1d:"
pkg-config --modversion dav1d

echo "FFmpeg configuration:"
"${INSTALL_DIR}/bin/ffmpeg" -version | grep configuration

# Clean up build directory
echo "Cleaning up build directory..."
cd "${SCRIPT_DIR}"
if [ -d "${BUILD_DIR}" ]; then
    rm -rf "${BUILD_DIR}"
    echo "Build directory cleaned up"
fi

echo "Build completed successfully!"
echo "Binaries and libraries are available at:"
echo "  ffmpeg:  ${SCRIPT_DIR}/ffmpeg"
echo "  ffprobe: ${SCRIPT_DIR}/ffprobe"
echo "  install: ${INSTALL_DIR}"
