import os
from pathlib import Path
from dotenv import load_dotenv
import torch

load_dotenv()

# Directory configuration
FOSCAM_DIR = Path("foscam")  # Main foscam directory
UPLOAD_DIR = FOSCAM_DIR  # Keep for backward compatibility

# Ensure directories exist
FOSCAM_DIR.mkdir(exist_ok=True)

# GPU and Model Configuration
MODEL_NAME = "Salesforce/blip2-t5-xl"  # T5-XL model for enhanced analysis
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
BATCH_SIZE = 2  # Reduced for T5-XL to avoid memory issues
MAX_LENGTH = 50
USE_8BIT_QUANTIZATION = True  # Enable 8-bit quantization for memory efficiency

# Video Processing
VIDEO_SAMPLE_RATE = 30  # Process every 30th frame

# AI Analysis Logging Configuration
AI_ANALYSIS_LOG_LEVEL = "INFO"  # Options: "DEBUG", "INFO", "WARNING"
# DEBUG: Log all analysis steps and detailed breakdowns
# INFO: Log comprehensive analysis results (default)
# WARNING: Log only alerts and errors

# Database
DATABASE_URL = "sqlite+aiosqlite:///./foscam_detections.db"

# Web server
HOST = "0.0.0.0"
PORT = 8000

# Foscam-specific file extensions and patterns
IMAGE_EXTENSIONS = {".jpg", ".jpeg"}
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi"}

# Foscam directory structure patterns
CAMERA_LOCATIONS = [
    "ami_frontyard_left",
    "beach_front_left", 
    "dock_right",
    "kitchen",
    "den",
    "dock_left"
]

# Foscam device naming patterns
FOSCAM_DEVICE_PATTERNS = [
    "FoscamCamera_",
    "R2_",
    "R2C_"
]

# Foscam file naming patterns
FOSCAM_IMAGE_PATTERNS = [
    "MDAlarm_",
    "HMDAlarm_"
]

FOSCAM_VIDEO_PATTERNS = [
    "MDalarm_"
]

# Date/time parsing patterns for foscam files
FOSCAM_DATETIME_PATTERNS = [
    "%Y%m%d-%H%M%S",  # For images: 20250712-213837
    "%Y%m%d_%H%M%S"   # For videos: 20250712_213837
]

# Enhanced T5-XL Configuration Notes:
# - MODEL_NAME: Uses Salesforce/blip2-t5-xl for enhanced analysis
# - BATCH_SIZE: Reduced to 2 for memory management
# - Processing generates structured output: SCENE | SECURITY | OBJECTS | ACTIVITY | SETTING | ALERTS
# - Expected VRAM usage: 18-22GB with 8-bit quantization
# - Enhanced analysis includes automatic alert detection and detailed breakdowns 