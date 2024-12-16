#!/usr/bin/env bash

# Build ffmpeg with dynamic linking using Linux Homebrew


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

# Function to check Homebrew dependencies
check_brew_deps() {
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
        
        # Libraries and their development files
        "expat"
        "gettext"
        "gperf"
        # Required libraries for FFmpeg
        "opus"
        "dav1d"
        "svt-av1"
        # VA-API support
        "libva"
    )

    echo "Checking Homebrew dependencies..."
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

# Update check_dependencies function
check_dependencies() {
    if ! command_exists brew; then
        echo "Error: Homebrew is not installed. Please install it first."
        echo "Visit https://brew.sh for installation instructions"
        exit 1
    fi
    
    # Set up environment to use Homebrew's tools and libraries
    eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
    
    check_brew_deps

    # Check for essential build tools
    local essential_tools=("git" "make" "pkg-config" "gcc")
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
    echo "Using Homebrew from: $(brew --prefix)"
    echo "Using GCC: $(which gcc)"
    echo "GCC version: $(gcc --version | head -n1)"
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

# Check system dependencies before starting any builds
check_dependencies

cd $BUILD_DIR

# Add this function before the FFmpeg build section
verify_compiler() {
    echo "Verifying compiler installation..."
    if ! gcc -v &>/dev/null; then
        echo "Error: gcc is not working properly"
        return 1
    fi
    
    # Create and run a simple test program
    local test_file="/tmp/test.c"
    echo "int main() { return 0; }" > "$test_file"
    if ! gcc -o /tmp/test "$test_file"; then
        echo "Error: gcc cannot create executables"
        return 1
    fi
    
    rm -f /tmp/test /tmp/test.c
    echo "Compiler verification successful"
    return 0
}

# Add this function after verify_compiler()
configure_ffmpeg() {
    local brew_prefix=$(brew --prefix)
    
    ./configure \
        --prefix="${INSTALL_DIR}" \
        --enable-gpl \
        --enable-version3 \
        --enable-shared \
        --disable-static \
        --disable-doc \
        --disable-debug \
        --disable-ffplay \
        --enable-ffprobe \
        --extra-cflags="-I${INSTALL_DIR}/include -I${brew_prefix}/include -O3" \
        --extra-ldflags="-L${INSTALL_DIR}/lib -L${brew_prefix}/lib -Wl,-rpath,${INSTALL_DIR}/lib -Wl,-rpath,${brew_prefix}/lib" \
        --extra-libs="-lpthread -lm" \
        --enable-libdav1d \
        --enable-libopus \
        --enable-libsvtav1 \
        --enable-vaapi \
        --cc="gcc" || {
            echo "FFmpeg configure failed. Checking config.log..."
            cat ffbuild/config.log
            exit 1
        }
}

# Build FFmpeg
git clone --depth=1 https://github.com/FFmpeg/FFmpeg.git
cd FFmpeg

# Verify compiler before proceeding
if ! verify_compiler; then
    echo "Error: Compiler verification failed"
    exit 1
fi

# Add diagnostic information
echo "Checking build environment..."
echo "gcc version: $(gcc -dumpversion)"
echo "Current directory: $(pwd)"
echo "PKG_CONFIG_PATH: ${PKG_CONFIG_PATH}"
echo "Install directory: ${INSTALL_DIR}"

# Configure FFmpeg with platform-specific settings
configure_ffmpeg

# Use number of CPU cores or fallback to 2 if nproc is not available
NPROC=$(nproc 2>/dev/null || echo 2)
echo "Building with $NPROC parallel jobs..."

make -j"${NPROC}" || {
    echo "FFmpeg make failed"
    exit 1
}

make install || {
    echo "FFmpeg installation failed"
    exit 1
}

# Update validation section
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
REQUIRED_LIBS=("libopus" "libdav1d" "libsvtav1" "vaapi")
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

# Verify linking
echo "Verifying dependencies..."
echo "Running ldd check..."
LDD_OUTPUT=$(ldd "${INSTALL_DIR}/bin/ffmpeg")
if [[ -n "$LDD_OUTPUT" ]]; then
    echo "Confirmed: FFmpeg is dynamically linked"
    echo "Dependencies:"
    echo "$LDD_OUTPUT"
else
    echo "Error: Could not verify FFmpeg dependencies"
    exit 1
fi

echo "FFmpeg validation completed!"
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

check_library_versions() {
    echo "Checking library versions..."
    echo "SVT-AV1:"
    pkg-config --modversion SvtAv1Enc
    pkg-config --libs SvtAv1Enc
    echo -e "\nOpus:"
    pkg-config --modversion opus
    pkg-config --libs opus
    echo -e "\ndav1d:"
    pkg-config --modversion dav1d
    pkg-config --libs dav1d
    echo
    echo "FFmpeg configuration:"
    "${SCRIPT_DIR}/ffmpeg" -version | grep -E "configuration|lib(svtav1|dav1d|opus)"
}

# Check library versions
check_library_versions

# Cleanup
rm -rf "${BUILD_DIR}"