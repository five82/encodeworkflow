"""Default configuration values."""

# Video encoding defaults
TARGET_VMAF = 95  # Target quality score (0-100)
PRESET = 8  # SVT-AV1 preset (0-13, higher is faster)
SVT_PARAMS = (
    "tune=0:"  # Visual tuning: 0=VQ, 1=PSNR
    "enable-qm=1:"  # Enable QM (improves subjective quality)
    "enable-hdr=1:"  # Enable HDR signal (auto-detected)
    "scd=1:"  # Enable scene change detection
    "film-grain=8:"  # Film grain synthesis level (0-50)
    "film-grain-denoise=1"  # Denoise before applying film grain
)
