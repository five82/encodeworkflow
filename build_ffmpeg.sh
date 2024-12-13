#!/usr/bin/env bash

# Build ffmpeg with static linking


cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "Build failed with exit code: $exit_code"
    fi
}

trap cleanup EXIT

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Ubuntu dependencies
check_ubuntu_deps() {
    local missing_deps=()
    local required_pkgs=(
        # Build tools
        "autoconf" "automake" "libtool"
        "git" "gcc" "g++" "clang" "make"
        "ninja-build" "meson" "cmake"
        "nasm" "yasm"
        "pkg-config"
        
        # System development files
        "libc6-dev"
        "linux-headers-generic"
        "binutils"
        "build-essential"
        "libstdc++-11-dev"
        "libgcc-11-dev"
        "libc6-dev"
        "gperf"
        "gettext"
        "libexpat1-dev"
    )

    echo "Checking Ubuntu dependencies..."
    for pkg in "${required_pkgs[@]}"; do
        if ! dpkg -l "$pkg" >/dev/null 2>&1; then
            missing_deps+=("$pkg")
        fi
    done

    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo "Missing required packages. Please install them with:"
        echo "sudo apt-get update && sudo apt-get install -y ${missing_deps[*]}"
        exit 1
    fi
}

# Function to check macOS dependencies
check_macos_deps() {
    local missing_deps=()
    local required_pkgs=(
        # Build tools
        "autoconf"
        "automake"
        "libtool"
        "git"
        "gcc"
        "make"
        "ninja"
        "meson"
        "cmake"
        "nasm"
        "yasm"
        "pkg-config"
    )

    echo "Checking macOS dependencies..."
    for pkg in "${required_pkgs[@]}"; do
        if ! brew list "$pkg" >/dev/null 2>&1; then
            missing_deps+=("$pkg")
        fi
    done

    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo "Missing required packages. Please install them with:"
        echo "brew install ${missing_deps[*]}"
        exit 1
    fi
}

# Check dependencies based on OS
check_dependencies() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if ! command_exists brew; then
            echo "Error: Homebrew is not installed. Please install it first."
            exit 1
        fi
        check_macos_deps
    elif command_exists apt-get; then
        check_ubuntu_deps
    else
        echo "Error: Unsupported system. This script supports Ubuntu and macOS."
        exit 1
    fi

    # Check for essential build tools regardless of OS
    local essential_tools=("git" "make" "pkg-config")
    local missing_tools=()

    for tool in "${essential_tools[@]}"; do
        if ! command_exists "$tool"; then
            missing_tools+=("$tool")
        fi
    done

    if [ ${#missing_tools[@]} -ne 0 ]; then
        echo "Error: Missing essential build tools: ${missing_tools[*]}"
        exit 1
    fi

    echo "All required dependencies are installed."
}

# Add this function after the check_dependencies function
check_build_dependencies() {
    echo "Checking build dependencies..."
    local missing_deps=()
    
    # Check pkg-config files
    local required_pc=(
        "opus"
        "SvtAv1Enc"
        "dav1d"
    )

    for pc in "${required_pc[@]}"; do
        echo "Checking ${pc}..."
        if ! PKG_CONFIG_PATH="${INSTALL_DIR}/lib/pkgconfig" pkg-config --exists "${pc}"; then
            missing_deps+=("${pc}")
            echo "  Not found!"
        else
            echo "  Found: $(PKG_CONFIG_PATH="${INSTALL_DIR}/lib/pkgconfig" pkg-config --modversion "${pc}")"
            echo "  Libs: $(PKG_CONFIG_PATH="${INSTALL_DIR}/lib/pkgconfig" pkg-config --libs "${pc}")"
        fi
    done

    # Check static libraries
    local required_libs=(
        "libopus.a"
        "libSvtAv1Enc.a"
        "libdav1d.a"
    )

    for lib in "${required_libs[@]}"; do
        echo "Checking ${lib}..."
        if ! find "${INSTALL_DIR}" -name "${lib}" | grep -q .; then
            missing_deps+=("${lib}")
            echo "  Not found!"
        else
            echo "  Found: $(find "${INSTALL_DIR}" -name "${lib}")"
        fi
    done

    if [ ${#missing_deps[@]} -ne 0 ]; then
        echo "Error: Missing required dependencies:"
        printf '%s\n' "${missing_deps[@]}"
        exit 1
    fi

    echo "All build dependencies are present."
}

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create and enter build directory
BUILD_DIR="${SCRIPT_DIR}/build"
mkdir -p $BUILD_DIR

# Near the top, after BUILD_DIR definition
INSTALL_DIR="${BUILD_DIR}/install"
mkdir -p $INSTALL_DIR

# Set up consistent environment variables
export PKG_CONFIG_PATH="${INSTALL_DIR}/lib/pkgconfig:${INSTALL_DIR}/lib64/pkgconfig"

# Check system dependencies before starting any builds
check_dependencies

cd $BUILD_DIR

# Build opus
git clone https://gitlab.xiph.org/xiph/opus.git
cd opus
autoreconf -fiv
./configure \
    --prefix="${INSTALL_DIR}" \
    --enable-static \
    --disable-shared
make -j$(nproc)
make install
cd $BUILD_DIR

# Build svt-av1-psy
git clone https://github.com/gianni-rosato/svt-av1-psy.git
cd svt-av1-psy
mkdir -p Build
cd Build
cmake .. -G"Unix Makefiles" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR}" \
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_DEC=OFF \
    -DSVT_AV1_LTO=ON \
    -DENABLE_AVX512=ON \
    -DNATIVE=ON \
    -DCMAKE_CXX_FLAGS="-O3" \
    -DCMAKE_C_FLAGS="-O3" \
    -DCMAKE_LD_FLAGS="-O3"
make -j $(nproc)
make install
cd $BUILD_DIR

# Build libdav1d
git clone --depth=1 https://code.videolan.org/videolan/dav1d.git
cd dav1d
meson setup build \
    --buildtype release \
    --default-library=static \
    --prefix="${INSTALL_DIR}" \
    --bindir="${INSTALL_DIR}/bin" \
    --libdir="${INSTALL_DIR}/lib" \
    -Denable_tools=false \
    -Denable_tests=false \
    -Denable_asm=true
ninja -C build
ninja -C build install
cd $BUILD_DIR

# Build FFmpeg
git clone --depth=1 https://github.com/FFmpeg/FFmpeg.git
cd FFmpeg

# Configure FFmpeg
./configure \
    --prefix="${INSTALL_DIR}" \
    --enable-gpl \
    --enable-version3 \
    --enable-static \
    --disable-shared \
    --disable-doc \
    --disable-debug \
    --disable-ffplay \
    --enable-ffprobe \
    --pkg-config-flags="--static" \
    --extra-cflags="-I${INSTALL_DIR}/include" \
    --extra-ldflags="-L${INSTALL_DIR}/lib -L${INSTALL_DIR}/lib64" \
    --extra-libs="-lpthread -lm" \
    --extra-ldexeflags="-static" \
    --enable-libdav1d \
    --enable-libopus \
    --enable-libsvtav1

make -j$(nproc)
make install
cd $BUILD_DIR

# Update validation section to use local installation
echo "Validating FFmpeg installation..."

# Check if ffmpeg and ffprobe are in our local installation
if ! "${INSTALL_DIR}/bin/ffmpeg" -version &> /dev/null; then
    echo "Error: ffmpeg binary failed to execute"
    exit 1
fi

if ! "${INSTALL_DIR}/bin/ffprobe" -version &> /dev/null; then
    echo "Error: ffprobe binary failed to execute"
    exit 1
fi

# Check for required libraries
echo "Checking FFmpeg configuration..."
REQUIRED_LIBS=("libopus" "libdav1d" "libsvtav1")
MISSING_LIBS=()

FFMPEG_CONFIG=$("${INSTALL_DIR}/bin/ffmpeg" -version | grep "configuration:")
for lib in "${REQUIRED_LIBS[@]}"; do
    if ! echo "$FFMPEG_CONFIG" | grep -q "$lib"; then
        MISSING_LIBS+=("$lib")
    fi
done

if [ ${#MISSING_LIBS[@]} -ne 0 ]; then
    echo "Error: FFmpeg is missing the following required libraries:"
    printf '%s\n' "${MISSING_LIBS[@]}"
    exit 1
fi

# Verify static linking
echo "Verifying static linking..."
if command -v ldd >/dev/null; then
    echo "Running ldd check..."
    LDD_OUTPUT=$(ldd "${INSTALL_DIR}/bin/ffmpeg" 2>&1)
    if [[ "$LDD_OUTPUT" =~ "not a dynamic executable" ]]; then
        echo "Confirmed: FFmpeg is statically linked"
    else
        echo "Error: FFmpeg is not statically linked. ldd output:"
        echo "$LDD_OUTPUT"
        exit 1
    fi
elif command -v otool >/dev/null; then
    echo "Running otool check..."
    if OTOOL_OUTPUT=$(otool -L "${INSTALL_DIR}/bin/ffmpeg" 2>&1) && \
       [[ $(echo "$OTOOL_OUTPUT" | wc -l) -le 2 ]]; then
        echo "Confirmed: FFmpeg appears to be statically linked"
    else
        echo "Error: FFmpeg is not statically linked. otool output:"
        echo "$OTOOL_OUTPUT"
        exit 1
    fi
else
    echo "Warning: Cannot verify static linking - neither ldd nor otool found"
fi

# At the end, after static linking verification:
echo "FFmpeg validation successful!"
echo "Build completed successfully!"
echo "Binaries location:"
echo "  ffmpeg:  ${INSTALL_DIR}/bin/ffmpeg"
echo "  ffprobe: ${INSTALL_DIR}/bin/ffprobe"

echo "Copying binaries to script directory..."
cp -v "${INSTALL_DIR}/bin/ffmpeg" "${SCRIPT_DIR}/ffmpeg"
cp -v "${INSTALL_DIR}/bin/ffprobe" "${SCRIPT_DIR}/ffprobe"
echo "Done! Binaries are available at:"
echo "  ffmpeg:  ${SCRIPT_DIR}/ffmpeg"
echo "  ffprobe: ${SCRIPT_DIR}/ffprobe"