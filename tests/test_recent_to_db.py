#!/usr/bin/env python3
"""
Process Recent Files and Save to Database
Processes the 5 most recent images and 2 most recent videos and saves results to database
"""

import sys
import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime
import time
import random
import os
import glob

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Import required modules directly
from src.ai_model import VisionLanguageModel
from src.models import Base, Detection, Camera, get_or_create_camera, get_alert_flags_from_alerts, extract_motion_detection_type
import src.config as config
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_recent_files():
    """Process recent files and save to database."""
    print("🧠 Processing Recent Files with Enhanced AI and Database Saving")
    print("=" * 60)
    
    # Find some sample files
    foscam_dir = Path("foscam")
    if not foscam_dir.exists():
        print("❌ Foscam directory not found")
        return
    
    # Look for image files and sort by modification time (newest first)
    image_patterns = ["*.jpg", "*.jpeg"]
    video_patterns = ["*.mkv", "*.mp4"]
    
    image_files = []
    for pattern in image_patterns:
        image_files.extend(glob.glob(str(foscam_dir / "**" / pattern), recursive=True))
    
    video_files = []
    for pattern in video_patterns:
        video_files.extend(glob.glob(str(foscam_dir / "**" / pattern), recursive=True))
    
    # Sort by modification time (newest first)
    image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    video_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    print(f"📁 Found {len(image_files)} images and {len(video_files)} videos")
    
    # Test with the most recent files
    test_images = image_files[:5] if len(image_files) >= 5 else image_files
    test_videos = video_files[:2] if len(video_files) >= 2 else video_files
    
    print(f"🎯 Processing {len(test_images)} most recent images and {len(test_videos)} most recent videos")
    
    # Show the dates of the files we're processing
    if test_images:
        print("\n📸 Recent Images to Process:")
        for i, img_path in enumerate(test_images, 1):
            mod_time = time.ctime(os.path.getmtime(img_path))
            print(f"  {i}. {Path(img_path).name} (Modified: {mod_time})")
    
    if test_videos:
        print("\n🎬 Recent Videos to Process:")
        for i, vid_path in enumerate(test_videos, 1):
            mod_time = time.ctime(os.path.getmtime(vid_path))
            print(f"  {i}. {Path(vid_path).name} (Modified: {mod_time})")
    
    try:
        # Import required modules
        from src.foscam_crawler import FoscamCrawler
        
        print(f"\n🚀 Initializing Foscam Crawler for targeted processing...")
        crawler = FoscamCrawler()
        await crawler.initialize()
        
        processed_count = 0
        success_count = 0
        
        # Process images
        print("\n📸 Processing Recent Images:")
        print("-" * 40)
        
        for i, image_path in enumerate(test_images, 1):
            print(f"\n{i}. Processing: {Path(image_path).name}")
            
            try:
                start_time = time.time()
                
                # Extract camera name from path
                camera_name = crawler.extract_camera_info_from_path(Path(image_path))
                
                # Check if already processed
                if await crawler.is_file_already_processed(Path(image_path)):
                    print(f"⏭️  Already processed, skipping")
                    continue
                
                # Process the file
                success = await crawler.process_file(Path(image_path), "image", camera_name)
                duration = time.time() - start_time
                
                if success:
                    print(f"✅ Success ({duration:.2f}s) - Saved to database")
                    success_count += 1
                else:
                    print(f"❌ Failed ({duration:.2f}s)")
                
                processed_count += 1
                    
            except Exception as e:
                print(f"❌ Exception: {str(e)}")
        
        # Process videos
        print("\n🎬 Processing Recent Videos:")
        print("-" * 40)
        
        for i, video_path in enumerate(test_videos, 1):
            print(f"\n{i}. Processing: {Path(video_path).name}")
            
            try:
                start_time = time.time()
                
                # Extract camera name from path
                camera_name = crawler.extract_camera_info_from_path(Path(video_path))
                
                # Check if already processed
                if await crawler.is_file_already_processed(Path(video_path)):
                    print(f"⏭️  Already processed, skipping")
                    continue
                
                # Process the file
                success = await crawler.process_file(Path(video_path), "video", camera_name)
                duration = time.time() - start_time
                
                if success:
                    print(f"✅ Success ({duration:.2f}s) - Saved to database")
                    success_count += 1
                else:
                    print(f"❌ Failed ({duration:.2f}s)")
                
                processed_count += 1
                    
            except Exception as e:
                print(f"❌ Exception: {str(e)}")
        
        print(f"\n📊 Processing Complete!")
        print(f"   Files processed: {processed_count}")
        print(f"   Successfully saved: {success_count}")
        print(f"📁 Check the dashboard - new detections should appear!")
        print(f"🔄 Refresh your browser to see the latest results")
        
        # Cleanup
        await crawler.cleanup()
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you're running from the project root with virtual environment activated")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(process_recent_files()) 