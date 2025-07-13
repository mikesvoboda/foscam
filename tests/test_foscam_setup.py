#!/usr/bin/env python3
"""
Test script to verify foscam setup and directory structure
"""
import asyncio
import logging
from pathlib import Path

from config import (
    FOSCAM_DIR, CAMERA_LOCATIONS, FOSCAM_DEVICE_PATTERNS,
    FOSCAM_IMAGE_PATTERNS, FOSCAM_VIDEO_PATTERNS,
    IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_foscam_structure():
    """Test foscam directory structure discovery."""
    print("🔍 Testing Foscam Directory Structure")
    print("=" * 50)
    
    # Check if foscam directory exists
    if not FOSCAM_DIR.exists():
        print(f"❌ Foscam directory not found: {FOSCAM_DIR}")
        return False
    
    print(f"✅ Foscam directory found: {FOSCAM_DIR}")
    
    # Discover camera structure
    cameras_found = []
    total_images = 0
    total_videos = 0
    
    for location in CAMERA_LOCATIONS:
        location_path = FOSCAM_DIR / location
        
        if not location_path.exists():
            print(f"⚠️  Location not found: {location}")
            continue
        
        print(f"\n📍 Scanning location: {location}")
        
        # Look for device directories
        for device_dir in location_path.iterdir():
            if device_dir.is_dir():
                device_name = device_dir.name
                is_known_device = any(
                    device_name.startswith(pattern) 
                    for pattern in FOSCAM_DEVICE_PATTERNS
                )
                
                if is_known_device:
                    cameras_found.append((location, device_name, device_dir))
                    print(f"  📷 Found camera: {device_name}")
                    
                    # Count media files
                    snap_dir = device_dir / "snap"
                    record_dir = device_dir / "record"
                    
                    if snap_dir.exists():
                        images = [f for f in snap_dir.iterdir() 
                                if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
                                and any(f.name.startswith(p) for p in FOSCAM_IMAGE_PATTERNS)]
                        total_images += len(images)
                        print(f"    📸 Images: {len(images)}")
                    
                    if record_dir.exists():
                        videos = [f for f in record_dir.iterdir() 
                                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
                                and any(f.name.startswith(p) for p in FOSCAM_VIDEO_PATTERNS)]
                        total_videos += len(videos)
                        print(f"    🎥 Videos: {len(videos)}")
                else:
                    print(f"  ⚠️  Unknown device pattern: {device_name}")
    
    print(f"\n📊 Summary:")
    print(f"  🎥 Total cameras found: {len(cameras_found)}")
    print(f"  📸 Total images: {total_images}")
    print(f"  🎬 Total videos: {total_videos}")
    print(f"  📁 Total media files: {total_images + total_videos}")
    
    return len(cameras_found) > 0

def test_file_naming():
    """Test file naming pattern recognition."""
    print("\n🏷️  Testing File Naming Patterns")
    print("=" * 50)
    
    # Test image patterns
    test_image_files = [
        "MDAlarm_20250712-213837.jpg",
        "HMDAlarm_20250712-213445.jpg",
        "someother_file.jpg",  # Should not match
        "MDAlarm_20250711-184756.jpg"
    ]
    
    print("📸 Image Pattern Testing:")
    for filename in test_image_files:
        matches = any(filename.startswith(pattern) for pattern in FOSCAM_IMAGE_PATTERNS)
        status = "✅" if matches else "❌"
        print(f"  {status} {filename}")
    
    # Test video patterns
    test_video_files = [
        "MDalarm_20250712_213830.mkv",
        "MDalarm_20250711_184731.mkv",
        "random_video.mkv",  # Should not match
        "MDalarm_20250710_161947.mkv"
    ]
    
    print("\n🎥 Video Pattern Testing:")
    for filename in test_video_files:
        matches = any(filename.startswith(pattern) for pattern in FOSCAM_VIDEO_PATTERNS)
        status = "✅" if matches else "❌"
        print(f"  {status} {filename}")

def test_camera_name_extraction():
    """Test camera name extraction from file paths."""
    print("\n🏷️  Testing Camera Name Extraction")
    print("=" * 50)
    
    # Sample file paths
    test_paths = [
        "foscam/ami_frontyard_left/FoscamCamera_00626EFE8B21/snap/MDAlarm_20250712-213837.jpg",
        "foscam/kitchen/R2C_00626EA776E4/record/MDalarm_20250712_213830.mkv",
        "foscam/beach_front_left/FoscamCamera_00626EFE546D/snap/HMDAlarm_20250712-213445.jpg"
    ]
    
    from ai_model import VisionLanguageModel
    
    # We'll test the camera name extraction method
    for path_str in test_paths:
        path = Path(path_str)
        print(f"\n📁 Path: {path_str}")
        
        # Extract camera name using the same logic as in ai_model.py
        try:
            path_parts = path.parts
            
            # Find the foscam directory index
            foscam_index = None
            for i, part in enumerate(path_parts):
                if part == "foscam":
                    foscam_index = i
                    break
            
            if foscam_index is not None and foscam_index + 2 < len(path_parts):
                camera_location = path_parts[foscam_index + 1]
                device_name = path_parts[foscam_index + 2]
                camera_name = f"{camera_location}_{device_name}"
                print(f"  📷 Extracted camera name: {camera_name}")
            else:
                print(f"  ❌ Could not extract camera name")
                
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")

def main():
    """Main test function."""
    print("🎥 Foscam System Setup Test")
    print("=" * 60)
    
    # Test directory structure
    structure_ok = test_foscam_structure()
    
    if not structure_ok:
        print("\n❌ Foscam directory structure test failed!")
        print("Please ensure your foscam data is properly organized.")
        return
    
    # Test file naming
    test_file_naming()
    
    # Test camera name extraction
    test_camera_name_extraction()
    
    print("\n✅ All tests completed!")
    print("\nNext steps:")
    print("1. Run './start.sh --crawler' to process existing files")
    print("2. Run './start.sh --monitor' to watch for new files")
    print("3. Run './start.sh --web' to start the web dashboard")

if __name__ == "__main__":
    main() 